from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
import sys

from pygls.lsp.server import LanguageServer

from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    DidOpenTextDocumentParams,
    DidChangeTextDocumentParams,
    Hover,
    HoverParams,
    MarkupContent,
    Position,
    PublishDiagnosticsParams,
    Range,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    CompletionParams,
)


from textx import TextXError
from textx.model import get_location

from bankdsl.parser import bankdsl_language
from bankdsl.semantic.validation import (
    validate_model,
    SemanticValidationError,
)


class BankCreditLanguageServer(LanguageServer):

    def __init__(self):
        super().__init__(
            name="bankcredit-language-server",
            version="0.1.0",
        )

        self.metamodel = bankdsl_language()

        # Diagnostics koje ćemo koristiti i za hover.
        self.diagnostics_by_uri: dict[str, list[Diagnostic]] = {}


server = BankCreditLanguageServer()


# ============================================================
# MODEL OBJECTS
# ============================================================

def iter_model_objects(obj, seen=None):

    if seen is None:
        seen = set()

    object_id = id(obj)

    if object_id in seen:
        return

    seen.add(object_id)

    if hasattr(obj, "_tx_position"):
        yield obj

    tx_attrs = getattr(obj.__class__, "_tx_attrs", {})

    for attr_name in tx_attrs:
        value = getattr(obj, attr_name, None)

        if isinstance(value, list):
            for item in value:
                if hasattr(item, "_tx_position"):
                    yield from iter_model_objects(item, seen)

        elif hasattr(value, "_tx_position"):
            yield from iter_model_objects(value, seen)


def get_model_objects(model):
    return list(iter_model_objects(model))

def extract_names_from_source(
    source: str,
    keyword: str,
) -> list[str]:
    pattern = rf"\b{re.escape(keyword)}\s+([A-Za-z_][A-Za-z0-9_]*)"

    return list(dict.fromkeys(
        re.findall(pattern, source)
    ))
# ============================================================
# TEXTX LOCATION -> LSP RANGE
# ============================================================

def object_range(obj) -> Range:

    location = get_location(obj)

    start_line = max(location["line"] - 1, 0)
    start_column = max(location["col"] - 1, 0)

    nchar = location.get("nchar", 1)

    return Range(
        start=Position(
            line=start_line,
            character=start_column,
        ),
        end=Position(
            line=start_line,
            character=start_column + max(nchar, 1),
        ),
    )


def get_object_start(obj) -> Position:
    location = get_location(obj)

    return Position(
        line=max(location["line"] - 1, 0),
        character=max(location["col"] - 1, 0),
    )


# ============================================================
# SOURCE RANGE HELPERS
# ============================================================

def source_position(source: str, offset: int) -> Position:

    before = source[:offset]

    line = before.count("\n")

    last_newline = before.rfind("\n")

    if last_newline == -1:
        character = offset
    else:
        character = offset - last_newline - 1

    return Position(
        line=line,
        character=character,
    )


def find_token_range(
    source: str,
    obj,
    token: str | None,
) -> Optional[Range]:

    if not token:
        return None

    if not hasattr(obj, "_tx_position"):
        return None

    start = obj._tx_position
    end = getattr(obj, "_tx_position_end", start + len(token))

    if start is None or end is None:
        return None

    fragment = source[start:end]

    index = fragment.find(token)

    if index == -1:
        return None

    absolute_start = start + index
    absolute_end = absolute_start + len(token)

    return Range(
        start=source_position(source, absolute_start),
        end=source_position(source, absolute_end),
    )


def diagnostic_range(
    source: str,
    obj,
    token: str | None = None,
) -> Range:

    token_range = find_token_range(
        source,
        obj,
        token,
    )

    if token_range is not None:
        return token_range

    return object_range(obj)


# ============================================================
# TEXTX PARSER ERROR
# ============================================================

def textx_error_to_diagnostic(
    exc: TextXError,
) -> Diagnostic:

    line = 0
    column = 0

    if hasattr(exc, "line") and exc.line:
        line = max(exc.line - 1, 0)

    if hasattr(exc, "col") and exc.col:
        column = max(exc.col - 1, 0)

    return Diagnostic(
        range=Range(
            start=Position(
                line=line,
                character=column,
            ),
            end=Position(
                line=line,
                character=column + 1,
            ),
        ),
        message=str(exc),
        severity=DiagnosticSeverity.Error,
        source="BankCreditDSL",
    )


# ============================================================
# SEMANTIC TARGET
# ============================================================

@dataclass
class SemanticTarget:
    obj: object | None
    token: str | None = None


# ============================================================
# OBJECT SEARCH HELPERS
# ============================================================

def object_name(obj) -> str:
    return str(
        getattr(obj, "name", "")
    ).strip()


def object_version(obj) -> str:
    return str(
        getattr(obj, "version", "")
    ).strip()


def find_by_name(
    objects,
    class_name: str,
    name: str,
    version: str | None = None,
):
    for obj in objects:

        if obj.__class__.__name__ != class_name:
            continue

        if object_name(obj) != name:
            continue

        if version is not None:
            if object_version(obj) != version:
                continue

        return obj

    return None


def find_product(
    objects,
    name: str,
    version: str | None = None,
):
    return find_by_name(
        objects,
        "Product",
        name,
        version,
    )


def find_workflow(
    objects,
    name: str,
    version: str | None = None,
):
    return find_by_name(
        objects,
        "WorkflowDef",
        name,
        version,
    )


def find_role(
    objects,
    name: str,
):
    return find_by_name(
        objects,
        "RoleDef",
        name,
    )


def find_step(
    objects,
    workflow_name: str,
    workflow_version: str,
    step_name: str,
):
    workflow = find_workflow(
        objects,
        workflow_name,
        workflow_version,
    )

    if workflow is None:
        return None

    for step in getattr(workflow, "steps", []) or []:
        if object_name(step) == step_name:
            return step

    return None


def find_state(
    objects,
    workflow_name: str,
    workflow_version: str,
    state_name: str,
):
    workflow = find_workflow(
        objects,
        workflow_name,
        workflow_version,
    )

    if workflow is None:
        return None

    for state in getattr(workflow, "states", []) or []:
        if object_name(state) == state_name:
            return state

    return None


def find_workflow_reference(
    objects,
    workflow_name: str,
    workflow_version: str,
):
    for obj in objects:

        if obj.__class__.__name__ != "WorkflowReference":
            continue

        name = str(
            getattr(obj, "workflow_name", "")
        ).strip()

        version = str(
            getattr(obj, "workflow_version", "")
        ).strip()

        if (
            name == workflow_name
            and version == workflow_version
        ):
            return obj

    return None


def find_product_child(
    product,
    class_name: str,
):
    for value_name in getattr(
        product.__class__,
        "_tx_attrs",
        {},
    ):

        value = getattr(
            product,
            value_name,
            None,
        )

        if value is None:
            continue

        if isinstance(value, list):
            for item in value:
                if item.__class__.__name__ == class_name:
                    return item

        elif value.__class__.__name__ == class_name:
            return value

    return None


# ============================================================
# SEMANTIC ERROR -> TARGET
# ============================================================

def resolve_semantic_target(
    model,
    error_message: str,
) -> SemanticTarget:

    objects = get_model_objects(model)

    # --------------------------------------------------------
    # ROLE
    # --------------------------------------------------------

    match = re.search(
        r"Role '([^']+)'",
        error_message,
    )

    if match:
        role_name = match.group(1)

        role = find_role(
            objects,
            role_name,
        )

        permission_match = re.search(
            r"permission '([^']+)'",
            error_message,
        )

        token = (
            permission_match.group(1)
            if permission_match
            else None
        )

        return SemanticTarget(
            role,
            token,
        )

    # --------------------------------------------------------
    # WORKFLOW + STEP
    # --------------------------------------------------------

    match = re.search(
        r"Workflow '([^']+)' version '([^']+)'",
        error_message,
    )

    if match:

        workflow_name = match.group(1)
        workflow_version = match.group(2)

        # State
        state_match = re.search(
            r"state '([^']+)'",
            error_message,
        )

        if state_match:

            state_name = state_match.group(1)

            state = find_state(
                objects,
                workflow_name,
                workflow_version,
                state_name,
            )

            if state is not None:
                return SemanticTarget(
                    state,
                    state_name,
                )

        # Step
        step_match = re.search(
            r"step '([^']+)'",
            error_message,
        )

        if step_match:

            step_name = step_match.group(1)

            step = find_step(
                objects,
                workflow_name,
                workflow_version,
                step_name,
            )

            if step is not None:

                action_match = re.search(
                    r"action '([^']+)'",
                    error_message,
                )

                next_match = re.search(
                    r"next step '([^']+)'",
                    error_message,
                )

                reject_match = re.search(
                    r"reject state '([^']+)'",
                    error_message,
                )

                role_match = re.search(
                    r"unknown role '([^']+)'",
                    error_message,
                )

                token = None

                if action_match:
                    token = action_match.group(1)

                elif next_match:
                    token = next_match.group(1)

                elif reject_match:
                    token = reject_match.group(1)

                elif role_match:
                    token = role_match.group(1)

                return SemanticTarget(
                    step,
                    token,
                )

        workflow = find_workflow(
            objects,
            workflow_name,
            workflow_version,
        )

        if workflow is not None:
            return SemanticTarget(
                workflow,
                None,
            )

    # --------------------------------------------------------
    # PRODUCT
    # --------------------------------------------------------

    product_match = re.search(
        r"Product '([^']+)' version '([^']+)'",
        error_message,
    )

    if product_match:

        product_name = product_match.group(1)
        product_version = product_match.group(2)

        product = find_product(
            objects,
            product_name,
            product_version,
        )

        if product is None:
            return SemanticTarget(
                None,
                None,
            )

        # Workflow reference
        workflow_ref_match = re.search(
            r"workflow '([^']+)' version '([^']+)'",
            error_message,
        )

        if workflow_ref_match:

            workflow_name = workflow_ref_match.group(1)
            workflow_version = workflow_ref_match.group(2)

            workflow_reference = find_workflow_reference(
                objects,
                workflow_name,
                workflow_version,
            )

            if workflow_reference is not None:
                return SemanticTarget(
                    workflow_reference,
                    workflow_version,
                )

        # Object workflow version mismatch
        declared_match = re.search(
            r"workflow_version '([^']+)'",
            error_message,
        )

        if declared_match:

            workflow_reference = find_product_child(
                product,
                "WorkflowReference",
            )

            if workflow_reference is not None:
                return SemanticTarget(
                    workflow_reference,
                    declared_match.group(1),
                )

        # Eligibility rule
        field_match = re.search(
            r"(?:field|for field|eligibility field) '([^']+)'",
            error_message,
        )

        if field_match:

            field_name = field_match.group(1)

            eligibility = find_product_child(
                product,
                "EligibilityBlock",
            )

            if eligibility is not None:

                for rule in getattr(
                    eligibility,
                    "rules",
                    [],
                ) or []:

                    if str(
                        getattr(rule, "field", "")
                    ).strip() == field_name:

                        return SemanticTarget(
                            rule,
                            field_name,
                        )

        # Duplicate eligibility rule
        duplicate_rule_match = re.search(
            r"eligibility rule \('([^']*)', '([^']*)', '([^']*)'\)",
            error_message,
        )

        if duplicate_rule_match:

            field = duplicate_rule_match.group(1)
            op = duplicate_rule_match.group(2)
            value = duplicate_rule_match.group(3)

            eligibility = find_product_child(
                product,
                "EligibilityBlock",
            )

            if eligibility is not None:

                for rule in getattr(
                    eligibility,
                    "rules",
                    [],
                ) or []:

                    if (
                        str(getattr(rule, "field", "")).strip()
                        == field
                        and str(getattr(rule, "op", "")).strip()
                        == op
                        and str(getattr(rule, "value", "")).strip()
                        == value
                    ):
                        return SemanticTarget(
                            rule,
                            field,
                        )

        # Fee
        fee_match = re.search(
            r"fee '([^']+)'",
            error_message,
        )

        if fee_match:

            fee_name = fee_match.group(1)

            fees_block = find_product_child(
                product,
                "FeesBlock",
            )

            if fees_block is not None:

                for fee in getattr(
                    fees_block,
                    "fees",
                    [],
                ) or []:

                    if str(
                        getattr(fee, "name", "")
                    ).strip() == fee_name:

                        return SemanticTarget(
                            fee,
                            fee_name,
                        )

        # Specific product child blocks
        if "interest" in error_message.lower():

            interest = find_product_child(
                product,
                "InterestBlock",
            )

            if interest is not None:
                return SemanticTarget(
                    interest,
                    None,
                )

        if (
            "repayment" in error_message.lower()
            or "grace_period" in error_message.lower()
        ):

            repayment = find_product_child(
                product,
                "RepaymentBlock",
            )

            if repayment is not None:
                return SemanticTarget(
                    repayment,
                    None,
                )

        if "scoring" in error_message.lower():

            scoring = find_product_child(
                product,
                "ScoringBlock",
            )

            if scoring is not None:
                return SemanticTarget(
                    scoring,
                    None,
                )

        if "eligibility" in error_message.lower():

            eligibility = find_product_child(
                product,
                "EligibilityBlock",
            )

            if eligibility is not None:
                return SemanticTarget(
                    eligibility,
                    None,
                )

        if "fees" in error_message.lower():

            fees = find_product_child(
                product,
                "FeesBlock",
            )

            if fees is not None:
                return SemanticTarget(
                    fees,
                    None,
                )

        # Generic product-level error
        return SemanticTarget(
            product,
            None,
        )

    # --------------------------------------------------------
    # PRODUCT WITHOUT VERSION
    # --------------------------------------------------------

    match = re.search(
        r"Product '([^']+)'",
        error_message,
    )

    if match:

        product_name = match.group(1)

        product = find_product(
            objects,
            product_name,
        )

        return SemanticTarget(
            product,
            None,
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return SemanticTarget(
        None,
        None,
    )


# ============================================================
# SEMANTIC DIAGNOSTICS
# ============================================================

def semantic_error_to_diagnostics(
    model,
    source: str,
    message: str,
) -> list[Diagnostic]:

    diagnostics = []

    for line in message.splitlines():

        line = line.strip()

        if not line:
            continue

        if line == "Semantic validation failed:":
            continue

        # Validator pravi:
        #
        # 1. Error...
        #
        # 2. Error...
        #
        if ". " in line:
            _, error_message = line.split(
                ". ",
                1,
            )
        else:
            error_message = line

        target = resolve_semantic_target(
            model,
            error_message,
        )

        if target.obj is not None:

            range_ = diagnostic_range(
                source,
                target.obj,
                target.token,
            )

        else:

            # Fallback ako iz nekog razloga
            # ne možemo povezati grešku sa model objektom.
            range_ = Range(
                start=Position(
                    line=0,
                    character=0,
                ),
                end=Position(
                    line=0,
                    character=1,
                ),
            )

        diagnostics.append(
            Diagnostic(
                range=range_,
                message=error_message,
                severity=DiagnosticSeverity.Error,
                source="BankCreditDSL",
            )
        )

    return diagnostics


# ============================================================
# DOCUMENT VALIDATION
# ============================================================

def validate_document(
    uri: str,
    source: str,
):
    diagnostics = []

    try:

        model = server.metamodel.model_from_str(
            source,
            file_name=uri,
        )

    except TextXError as exc:

        diagnostics.append(
            textx_error_to_diagnostic(exc)
        )

        return diagnostics

    try:

        validate_model(model)

    except SemanticValidationError as exc:

        diagnostics.extend(
            semantic_error_to_diagnostics(
                model,
                source,
                str(exc),
            )
        )

    return diagnostics


# ============================================================
# PUBLISH DIAGNOSTICS
# ============================================================

def publish_diagnostics(
    ls: LanguageServer,
    uri: str,
    diagnostics: list[Diagnostic],
):

    ls.diagnostics_by_uri[uri] = diagnostics

    ls.text_document_publish_diagnostics(
        PublishDiagnosticsParams(
            uri=uri,
            diagnostics=diagnostics,
        )
    )


# ============================================================
# DID OPEN
# ============================================================

@server.feature("textDocument/didOpen")
async def did_open(
    ls: LanguageServer,
    params: DidOpenTextDocumentParams,
):

    document = ls.workspace.get_text_document(
        params.text_document.uri
    )

    diagnostics = validate_document(
        document.uri,
        document.source,
    )

    publish_diagnostics(
        ls,
        document.uri,
        diagnostics,
    )


# ============================================================
# DID CHANGE
# ============================================================

@server.feature("textDocument/didChange")
async def did_change(
    ls: LanguageServer,
    params: DidChangeTextDocumentParams,
):

    document = ls.workspace.get_text_document(
        params.text_document.uri
    )

    diagnostics = validate_document(
        document.uri,
        document.source,
    )

    publish_diagnostics(
        ls,
        document.uri,
        diagnostics,
    )


# ============================================================
# HOVER
# ============================================================

def position_in_range(
    position: Position,
    range_: Range,
) -> bool:

    if position.line < range_.start.line:
        return False

    if position.line > range_.end.line:
        return False

    if (
        position.line == range_.start.line
        and position.character < range_.start.character
    ):
        return False

    if (
        position.line == range_.end.line
        and position.character > range_.end.character
    ):
        return False

    return True


@server.feature("textDocument/hover")
async def hover(
    ls: LanguageServer,
    params: HoverParams,
):

    uri = params.text_document.uri

    diagnostics = ls.diagnostics_by_uri.get(
        uri,
        [],
    )

    if not diagnostics:
        return None

    position = params.position

    matching = []

    for diagnostic in diagnostics:

        if position_in_range(
            position,
            diagnostic.range,
        ):
            matching.append(diagnostic)

    if not matching:
        return None

    lines = []

    for diagnostic in matching:

        lines.append(
            f"**{diagnostic.source or 'BankCreditDSL'}**"
        )

        lines.append("")

        lines.append(
            diagnostic.message
        )

        lines.append("")

    return Hover(
        contents=MarkupContent(
            kind="markdown",
            value="\n".join(lines),
        )
    )


###############################################
#Completition
def get_word_before_cursor(source: str, position: Position) -> str:
    lines = source.splitlines()

    if position.line >= len(lines):
        return ""

    line = lines[position.line]
    before_cursor = line[:position.character]

    match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", before_cursor)

    if match:
        return match.group(0)

    return ""

def completion_item(
    label: str,
    kind: CompletionItemKind,
    detail: str | None = None,
):
    return CompletionItem(
        label=label,
        kind=kind,
        detail=detail,
    )


def model_names(model, class_name: str) -> list[str]:
    if model is None:
        return []

    result = []

    for obj in get_model_objects(model):
        if obj.__class__.__name__ != class_name:
            continue

        name = object_name(obj)

        if name and name not in result:
            result.append(name)

    return result

def workflow_versions(model) -> list[tuple[str, str]]:
    if model is None:
        return []

    result = []

    for obj in get_model_objects(model):
        if obj.__class__.__name__ != "WorkflowDef":
            continue

        name = object_name(obj)
        version = object_version(obj)

        if name and version:
            result.append((name, version))

    return result



@server.feature(
    "textDocument/completion",
    CompletionOptions(
        trigger_characters=[":"],
    ),
)
async def completion(
    ls: LanguageServer,
    params: CompletionParams,
):

    document = ls.workspace.get_text_document(
        params.text_document.uri
    )

    source = document.source
    position = params.position

    # ---------------------------------------------------------
    # Text before cursor
    # ---------------------------------------------------------

    lines = source.splitlines()

    if position.line >= len(lines):
        return None

    text_before_cursor = "\n".join(
        lines[:position.line]
        + [lines[position.line][:position.character]]
    )

    current_line = lines[position.line][:position.character]

    # ---------------------------------------------------------
    # Current word / prefix
    # ---------------------------------------------------------

    match = re.search(
        r"[A-Za-z_][A-Za-z0-9_]*$",
        current_line,
    )

    prefix = match.group(0) if match else ""

    print(
        "COMPLETION:",
        repr(current_line),
        repr(prefix),
        file=sys.stderr,
        flush=True,
    )
    # ---------------------------------------------------------
    # Parse current model
    # ---------------------------------------------------------

    try:
        model = ls.metamodel.model_from_str(
            source,
            file_name=document.uri,
        )
    except TextXError:
        model = None

    # ---------------------------------------------------------
    # Collect model objects
    # ---------------------------------------------------------
    roles = []
    workflows = []
    products = []
    states = []
    steps = []

    # ---------------------------------------------------------
    # First try to use the parsed textX model
    # ---------------------------------------------------------

    if model is not None:

        for obj in get_model_objects(model):

            class_name = obj.__class__.__name__
            name = object_name(obj)

            if not name:
                continue

            if class_name == "RoleDef":
                if name not in roles:
                    roles.append(name)

            elif class_name == "WorkflowDef":
                if name not in workflows:
                    workflows.append(name)

            elif class_name == "Product":
                if name not in products:
                    products.append(name)

            elif class_name == "WorkflowState":
                if name not in states:
                    states.append(name)

            elif class_name == "ProcessStep":
                if name not in steps:
                    steps.append(name)


    # ---------------------------------------------------------
    # Fallback: document may currently contain syntax errors
    # ---------------------------------------------------------

    if not roles:
        roles = extract_names_from_source(
            source,
            "role",
        )

    if not workflows:
        workflows = extract_names_from_source(
            source,
            "workflow",
        )

    if not products:
        products = extract_names_from_source(
            source,
            "product",
        )

    if not states:
        states = extract_names_from_source(
            source,
            "state",
        )

    if not steps:
        steps = extract_names_from_source(
            source,
            "step",
        )

    # ---------------------------------------------------------
    # Helper
    # ---------------------------------------------------------

    def make_items(
        values,
        kind,
        detail,
    ):
        return [
            CompletionItem(
                label=value,
                kind=kind,
                detail=detail,
            )
            for value in values
            if not prefix
            or value.lower().startswith(prefix.lower())
        ]

    # =========================================================
    # REFERENCES
    # =========================================================

    # handled_by:
    if re.search(
        r"handled_by\s*:\s*[A-Za-z_0-9]*$",
        current_line,
        re.IGNORECASE,
    ):
        return CompletionList(
            is_incomplete=False,
            items=make_items(
                roles,
                CompletionItemKind.Reference,
                "Role",
            ),
        )

    # workflow:
    if re.search(
        r"workflow\s*:\s*[A-Za-z_0-9]*$",
        current_line,
        re.IGNORECASE,
    ):
        return CompletionList(
            is_incomplete=False,
            items=make_items(
                workflows,
                CompletionItemKind.Reference,
                "Workflow",
            ),
        )

    # on_reject:
    if re.search(
        r"on_reject\s*:\s*[A-Za-z_0-9]*$",
        current_line,
        re.IGNORECASE,
    ):
        return CompletionList(
            is_incomplete=False,
            items=make_items(
                states,
                CompletionItemKind.EnumMember,
                "Workflow state",
            ),
        )

    # on_success:
    if re.search(
        r"on_success\s*:\s*[A-Za-z_0-9]*$",
        current_line,
        re.IGNORECASE,
    ):
        return CompletionList(
            is_incomplete=False,
            items=make_items(
                states,
                CompletionItemKind.EnumMember,
                "Workflow state",
            ),
        )

    # next:
    if re.search(
        r"next\s*:\s*[A-Za-z_0-9]*$",
        current_line,
        re.IGNORECASE,
    ):
        return CompletionList(
            is_incomplete=False,
            items=make_items(
                steps + states,
                CompletionItemKind.Reference,
                "Workflow node",
            ),
        )

    # =========================================================
    # REQUIRE
    # =========================================================

    # require <field> <operator>
    if re.search(
        r"require\s+[A-Za-z_][A-Za-z0-9_]*\s*$",
        current_line,
        re.IGNORECASE,
    ):
        operators = [
            ">=",
            "<=",
            "==",
            "!=",
            ">",
            "<",
        ]

        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(
                    label=operator,
                    kind=CompletionItemKind.Operator,
                    detail="Comparison operator",
                )
                for operator in operators
            ],
        )

    # require <field>
    if re.search(
        r"require\s+[A-Za-z_][A-Za-z0-9_]*$",
        current_line,
        re.IGNORECASE,
    ):
        fields = [
            "age",
            "income",
            "credit_score",
            "employment_years",
        ]

        return CompletionList(
            is_incomplete=False,
            items=make_items(
                fields,
                CompletionItemKind.Field,
                "Eligibility field",
            ),
        )

    # require
    if re.search(
        r"require\s*$",
        current_line,
        re.IGNORECASE,
    ):
        fields = [
            "age",
            "income",
            "credit_score",
            "employment_years",
        ]

        return CompletionList(
            is_incomplete=False,
            items=make_items(
                fields,
                CompletionItemKind.Field,
                "Eligibility field",
            ),
        )

    # =========================================================
    # ROLE BODY
    # =========================================================

    if re.search(
        r"\brole\s+\w+\s*\{[^{}]*$",
        text_before_cursor,
        re.DOTALL,
    ):
        keywords = [
            "description",
            "permissions",
        ]

        return CompletionList(
            is_incomplete=False,
            items=make_items(
                keywords,
                CompletionItemKind.Keyword,
                "Role property",
            ),
        )

    # =========================================================
    # WORKFLOW BODY
    # =========================================================

    if re.search(
        r"\bworkflow\s+\w+\s+version\s+\"[^\"]*\"\s*\{[^{}]*$",
        text_before_cursor,
        re.DOTALL,
    ):
        keywords = [
            "step",
            "state",
        ]

        return CompletionList(
            is_incomplete=False,
            items=make_items(
                keywords,
                CompletionItemKind.Keyword,
                "Workflow element",
            ),
        )

    # =========================================================
    # STEP BODY
    # =========================================================

    if re.search(
        r"\bstep\s+\w+\s*\{[^{}]*$",
        text_before_cursor,
        re.DOTALL,
    ):
        keywords = [
            "handled_by",
            "action",
            "on_reject",
            "on_success",
            "next",
        ]

        return CompletionList(
            is_incomplete=False,
            items=make_items(
                keywords,
                CompletionItemKind.Keyword,
                "Step property",
            ),
        )

    # =========================================================
    # PRODUCT BODY
    # =========================================================

    if re.search(
        r"\bproduct\s+\w+\s+version\s+\"[^\"]*\"\s*\{[^{}]*$",
        text_before_cursor,
        re.DOTALL,
    ):
        keywords = [
            "type",
            "valid_from",
            "valid_to",
            "amount",
            "term",
            "workflow",
            "interest",
            "eligibility",
            "fees",
            "repayment",
            "scoring",
        ]

        return CompletionList(
            is_incomplete=False,
            items=make_items(
                keywords,
                CompletionItemKind.Keyword,
                "Product property",
            ),
        )

    # =========================================================
    # TOP LEVEL
    # =========================================================

    keywords = [
        "product",
        "role",
        "workflow",
    ]

    return CompletionList(
        is_incomplete=False,
        items=make_items(
            keywords,
            CompletionItemKind.Keyword,
            "Bank Credit DSL",
        ),
    )

if __name__ == "__main__":
    server.start_io()