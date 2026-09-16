from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable


class SemanticValidationError(ValueError):
    pass


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _number(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise SemanticValidationError(f"Invalid numeric value: {value!r}")


def _parse_date(value, field_name: str) -> date:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        raise SemanticValidationError(
            f"{field_name} must use YYYY-MM-DD format, got {_text(value)!r}"
        )


def _name(obj) -> str:
    return _text(getattr(obj, "name", ""))


def _version(obj) -> str:
    return _text(getattr(obj, "version", ""))


def _names(objects: Iterable) -> set[str]:
    return {_name(x) for x in objects if _name(x)}


def validate_model(model) -> None:
    errors: list[str] = []

    roles = list(getattr(model, "roles", []) or [])
    workflows = list(getattr(model, "workflows", []) or [])
    products = list(getattr(model, "products", []) or [])

    errors.extend(_validate_roles(roles))
    errors.extend(_validate_workflows(workflows, roles))
    errors.extend(_validate_products(products, workflows))

    if errors:
        message = "Semantic validation failed:\n" + "\n".join(
            f"  {i}. {error}" for i, error in enumerate(errors, 1)
        )
        raise SemanticValidationError(message)


# ROLES

def _validate_roles(roles) -> list[str]:
    errors = []

    # Role names unique.
    groups = defaultdict(list)
    for role in roles:
        groups[_name(role)].append(role)

    for name, items in groups.items():
        if len(items) > 1:
            errors.append(f"Role '{name}' is defined more than once.")

    for role in roles:
        role_name = _name(role)
        permissions = list(getattr(role, "permissions", []) or [])

        # At least one permission.
        if not permissions:
            errors.append(
                f"Role '{role_name}' must define at least one permission."
            )

        # Permission IDs unique inside one role.
        normalized = [_text(p) for p in permissions]
        duplicates = {
            p for p in normalized
            if normalized.count(p) > 1
        }
        for permission in sorted(duplicates):
            errors.append(
                f"Role '{role_name}' contains duplicate permission "
                f"'{permission}'."
            )

        # Empty permission names
        if any(not p for p in normalized):
            errors.append(
                f"Role '{role_name}' contains an empty permission."
            )

    return errors


# WORKFLOWS

def _validate_workflows(workflows, roles) -> list[str]:
    errors = []
    role_names = _names(roles)

    # name + version
    identity_groups = defaultdict(list)
    name_groups = defaultdict(list)

    for workflow in workflows:
        identity = (_name(workflow), _version(workflow))
        identity_groups[identity].append(workflow)
        name_groups[_name(workflow)].append(workflow)

    for (name, version), items in identity_groups.items():
        if len(items) > 1:
            errors.append(
                f"Workflow '{name}' version '{version}' is defined more "
                f"than once."
            )

    for workflow in workflows:
        wf_name = _name(workflow)
        wf_version = _version(workflow)
        steps = list(getattr(workflow, "steps", []) or [])
        states = list(getattr(workflow, "states", []) or [])

        # Version=
        if not wf_version:
            errors.append(
                f"Workflow '{wf_name}' must have a non-empty version."
            )

        # Steps.
        if not steps:
            errors.append(
                f"Workflow '{wf_name}' version '{wf_version}' must contain "
                f"at least one step."
            )

        # States.
        state_groups = defaultdict(list)
        for state in states:
            state_groups[_name(state)].append(state)

        for state_name, items in state_groups.items():
            if len(items) > 1:
                errors.append(
                    f"Workflow '{wf_name}' version '{wf_version}' contains "
                    f"duplicate state '{state_name}'."
                )

        # Step names.
        step_groups = defaultdict(list)
        for step in steps:
            step_groups[_name(step)].append(step)

        for step_name, items in step_groups.items():
            if len(items) > 1:
                errors.append(
                    f"Workflow '{wf_name}' version '{wf_version}' contains "
                    f"duplicate step '{step_name}'."
                )

        step_names = _names(steps)
        state_names = _names(states)

        # Recommended/required terminal states
        if "Odobreno" not in state_names:
            errors.append(
                f"Workflow '{wf_name}' version '{wf_version}' must define "
                f"terminal state 'Odobreno'."
            )

        if "Odbijeno" not in state_names:
            errors.append(
                f"Workflow '{wf_name}' version '{wf_version}' must define "
                f"terminal state 'Odbijeno'."
            )

        for step in steps:
            step_name = _name(step)
            role = getattr(step, "role", None)
            action = _text(getattr(step, "action", None))
            next_step = getattr(step, "next", None)
            reject_state = getattr(step, "on_reject", None)
            success_state = getattr(step, "on_success", None)

            if role is None:
                errors.append(
                    f"Workflow '{wf_name}' version '{wf_version}', step "
                    f"'{step_name}' must reference a role."
                )
            else:
                role_name = _name(role)
                if role_name not in role_names:
                    errors.append(
                        f"Workflow '{wf_name}' version '{wf_version}', step "
                        f"'{step_name}' references unknown role "
                        f"'{role_name}'."
                    )

                # If action is defined, the assigned role must have it.
                if action:
                    permissions = {
                        _text(p)
                        for p in (getattr(role, "permissions", []) or [])
                    }
                    if action not in permissions:
                        errors.append(
                            f"Workflow '{wf_name}' version '{wf_version}', "
                            f"step '{step_name}' uses action '{action}', but "
                            f"role '{role_name}' does not have permission "
                            f"'{action}'."
                        )

            if next_step is not None:
                next_name = _name(next_step)
                if next_name == step_name:
                    errors.append(
                        f"Workflow '{wf_name}' version '{wf_version}', step "
                        f"'{step_name}' cannot point to itself with 'next'."
                    )
                if next_name not in step_names and next_name not in state_names:
                    errors.append(
                        f"Workflow '{wf_name}' version '{wf_version}', step "
                        f"'{step_name}' references unknown next step "
                        f"'{next_name}'."
                    )

            if reject_state is not None:
                reject_name = _name(reject_state)
                if reject_name not in state_names:
                    errors.append(
                        f"Workflow '{wf_name}' version '{wf_version}', step "
                        f"'{step_name}' references unknown reject state "
                        f"'{reject_name}'."
                    )

            if success_state is not None:
                success_name = _name(success_state)
                if success_name not in state_names:
                    errors.append(
                        f"Workflow '{wf_name}' version '{wf_version}', step "
                        f"'{step_name}' references unknown success state "
                        f"'{success_name}'."
                    )

        # one entry step
        if steps:
            incoming = { _name(step.next) for step in steps
                         if getattr(step, "next", None) is not None }
            entry_candidates = step_names - incoming
            if len(entry_candidates) != 1:
                errors.append(
                    f"Workflow '{wf_name}' version '{wf_version}' must have "
                    f"exactly one entry step; found "
                    f"{len(entry_candidates)} ({sorted(entry_candidates)})."
                )

    return errors


# PRODUCTS

def _validate_products(products, workflows) -> list[str]:
    errors = []

    # Product identity (name, version)
    identity_groups = defaultdict(list)
    name_groups = defaultdict(list)

    for product in products:
        identity = (_name(product), _version(product))
        identity_groups[identity].append(product)
        name_groups[_name(product)].append(product)

    for (name, version), items in identity_groups.items():
        if len(items) > 1:
            errors.append(
                f"Product '{name}' version '{version}' is defined more "
                f"than once."
            )

    for product in products:
        product_name = _name(product)
        product_version = _version(product)

        errors.extend(
            _validate_product_dates(product)
        )
        errors.extend(
            _validate_product_amount_and_term(product)
        )
        errors.extend(
            _validate_product_workflow(product, workflows)
        )
        errors.extend(
            _validate_interest(product)
        )
        errors.extend(
            _validate_eligibility(product)
        )
        errors.extend(
            _validate_fees(product)
        )
        errors.extend(
            _validate_repayment(product)
        )
        errors.extend(
            _validate_scoring(product)
        )

        # Version not empty
        if not product_version:
            errors.append(
                f"Product '{product_name}' must have a non-empty version."
            )

    # overlap between versions
    for product_name, versions in name_groups.items():
        errors.extend(
            _validate_product_version_periods(product_name, versions)
        )

    return errors


def _validate_product_dates(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)

    valid_from_raw = getattr(product, "valid_from", None)
    valid_to_raw = getattr(product, "valid_to", None)

    valid_from = None
    valid_to = None

    if valid_from_raw:
        try:
            valid_from = _parse_date(valid_from_raw, f"Product '{name}' valid_from")
        except SemanticValidationError as exc:
            errors.append(str(exc))

    if valid_to_raw:
        try:
            valid_to = _parse_date(valid_to_raw, f"Product '{name}' valid_to")
        except SemanticValidationError as exc:
            errors.append(str(exc))

    if valid_from and valid_to and valid_from > valid_to:
        errors.append(
            f"Product '{name}' version '{version}' has valid_from "
            f"after valid_to."
        )

    return errors


def _validate_product_version_periods(product_name: str, versions) -> list[str]:
    errors = []

    parsed = []

    for product in versions:
        version = _version(product)
        valid_from_raw = getattr(product, "valid_from", None)
        valid_to_raw = getattr(product, "valid_to", None)

        try:
            start = (
                _parse_date(valid_from_raw, "valid_from")
                if valid_from_raw else date.min
            )
            end = (
                _parse_date(valid_to_raw, "valid_to")
                if valid_to_raw else date.max
            )
            parsed.append((version, start, end))
        except SemanticValidationError:
            # Date-format errors are already reported elsewhere.
            continue

    for i, (v1, start1, end1) in enumerate(parsed):
        for v2, start2, end2 in parsed[i + 1:]:
            if max(start1, start2) <= min(end1, end2):
                errors.append(
                    f"Product '{product_name}' versions '{v1}' and '{v2}' "
                    f"have overlapping validity periods."
                )

    return errors


def _validate_product_amount_and_term(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)

    amount_min = _number(getattr(product, "amount_min", 0))
    amount_max = _number(getattr(product, "amount_max", 0))
    term_min = int(getattr(product, "term_min", 0))
    term_max = int(getattr(product, "term_max", 0))

    if amount_min <= 0:
        errors.append(
            f"Product '{name}' version '{version}' amount_min must be > 0."
        )

    if amount_max <= 0:
        errors.append(
            f"Product '{name}' version '{version}' amount_max must be > 0."
        )

    if amount_min > amount_max:
        errors.append(
            f"Product '{name}' version '{version}' amount_min must be "
            f"<= amount_max."
        )

    if term_min <= 0:
        errors.append(
            f"Product '{name}' version '{version}' term_min must be > 0."
        )

    if term_max <= 0:
        errors.append(
            f"Product '{name}' version '{version}' term_max must be > 0."
        )

    if term_min > term_max:
        errors.append(
            f"Product '{name}' version '{version}' term_min must be "
            f"<= term_max."
        )

    currency = _text(getattr(product, "currency", None))
    if not currency:
        errors.append(
            f"Product '{name}' version '{version}' must define a currency."
        )

    return errors

def _validate_product_workflow(product, workflows):
    errors = []

    name = _name(product)
    version = _version(product)

    workflow_ref = getattr(product, "workflow", None)

    if workflow_ref is None:
        errors.append(
            f"Product '{name}' version '{version}' must reference a workflow."
        )
        return errors

    workflow_name = _text(
        getattr(workflow_ref, "workflow_name", None)
    )

    workflow_version = _text(
        getattr(workflow_ref, "workflow_version", None)
    )

    if not workflow_name:
        errors.append(
            f"Product '{name}' version '{version}' must define workflow name."
        )

    if not workflow_version:
        errors.append(
            f"Product '{name}' version '{version}' must define workflow version."
        )

    matching_workflows = [
        workflow
        for workflow in workflows
        if _name(workflow) == workflow_name
        and _version(workflow) == workflow_version
    ]

    if not matching_workflows:
        errors.append(
            f"Product '{name}' version '{version}' references workflow "
            f"'{workflow_name}' version '{workflow_version}', "
            f"but that exact workflow version does not exist."
        )

    return errors
# INTEREST

def _validate_interest(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)
    interest = getattr(product, "interest", None)

    if interest is None:
        errors.append(
            f"Product '{name}' version '{version}' must define interest."
        )
        return errors

    interest_type = _text(getattr(interest, "type", None)).lower()
    rate = _number(getattr(interest, "rate", 0))
    reference = _text(getattr(interest, "reference", None))

    if not interest_type:
        errors.append(
            f"Product '{name}' version '{version}' interest type cannot be empty."
        )

    if rate < 0:
        errors.append(
            f"Product '{name}' version '{version}' interest rate cannot be negative."
        )

    if rate > 100:
        errors.append(
            f"Product '{name}' version '{version}' interest rate cannot exceed 100%."
        )

    if interest_type == "variable" and not reference:
        errors.append(
            f"Product '{name}' version '{version}' has variable interest "
            f"but no reference rate."
        )

    if interest_type == "fixed" and reference:
        errors.append(
            f"Product '{name}' version '{version}' has fixed interest but "
            f"also defines reference '{reference}'."
        )

    return errors

# ELIGIBILITY

def _validate_eligibility(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)

    eligibility = getattr(product, "eligibility", None)
    if eligibility is None:
        errors.append(
            f"Product '{name}' version '{version}' must define eligibility."
        )
        return errors

    rules = list(getattr(eligibility, "rules", []) or [])

    if not rules:
        errors.append(
            f"Product '{name}' version '{version}' eligibility must contain "
            f"at least one rule."
        )

    total_weight = Decimal("0")
    fields = defaultdict(list)

    for rule in rules:
        field = _text(getattr(rule, "field", None))
        op = _text(getattr(rule, "op", None))
        weight_raw = getattr(rule, "weight", None)
        value = getattr(rule, "value", None)

        if not field:
            errors.append(
                f"Product '{name}' version '{version}' contains an "
                f"eligibility rule with an empty field."
            )

        fields[field].append(rule)

        if op not in {">=", "<=", "==", "!=", ">", "<"}:
            errors.append(
                f"Product '{name}' version '{version}' uses invalid "
                f"eligibility operator '{op}'."
            )

        if weight_raw is not None:
            weight = _number(weight_raw)

            if weight < 0:
                errors.append(
                    f"Product '{name}' version '{version}' has negative "
                    f"eligibility weight for field '{field}'."
                )

            if weight == 0:
                errors.append(
                    f"Product '{name}' version '{version}' has zero "
                    f"eligibility weight for field '{field}'."
                )

            total_weight += weight

        if value is None:
            errors.append(
                f"Product '{name}' version '{version}' has an eligibility "
                f"rule for '{field}' without a value."
            )

    # Duplicate rule
    seen = set()
    for rule in rules:
        key = (
            _text(getattr(rule, "field", None)),
            _text(getattr(rule, "op", None)),
            _text(getattr(rule, "value", None)),
        )
        if key in seen:
            errors.append(
                f"Product '{name}' version '{version}' contains duplicate "
                f"eligibility rule {key}."
            )
        seen.add(key)

    for field in ("age", "monthly_income", "employment_months", "credit_score"):
        field_rules = fields.get(field, [])
        for rule in field_rules:
            if _text(getattr(rule, "op", None)) in {"==", "!="}:
                continue
            value = getattr(rule, "value", None)
            try:
                numeric_value = _number(value)
            except SemanticValidationError:
                continue

            if numeric_value < 0:
                errors.append(
                    f"Product '{name}' version '{version}' has negative "
                    f"value for eligibility field '{field}'."
                )

    # Ratios not in  0..1.
    for field in ("loan_to_value_ratio", "debt_to_income_ratio"):
        for rule in fields.get(field, []):
            try:
                value = _number(getattr(rule, "value", None))
            except SemanticValidationError:
                continue

            if not Decimal("0") <= value <= Decimal("1"):
                errors.append(
                    f"Product '{name}' version '{version}' has {field}={value}; "
                    f"expected a ratio between 0 and 1."
                )

    return errors


# FEES

def _validate_fees(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)

    fees_block = getattr(product, "fees", None)
    if fees_block is None:
        errors.append(
            f"Product '{name}' version '{version}' must define fees."
        )
        return errors

    fees = list(getattr(fees_block, "fees", []) or [])

    if not fees:
        errors.append(
            f"Product '{name}' version '{version}' fees block must contain "
            f"at least one fee."
        )

    fee_names = defaultdict(list)

    for fee in fees:
        fee_name = _text(getattr(fee, "name", None))
        percent = _number(getattr(fee, "percent", 0))
        trigger = _text(getattr(fee, "trigger", None))
        frequency = _text(getattr(fee, "freq", None))

        fee_names[fee_name].append(fee)

        if not fee_name:
            errors.append(
                f"Product '{name}' version '{version}' contains a fee "
                f"without a name."
            )

        if percent < 0:
            errors.append(
                f"Product '{name}' version '{version}' fee '{fee_name}' "
                f"cannot have a negative percentage."
            )

        if percent > 100:
            errors.append(
                f"Product '{name}' version '{version}' fee '{fee_name}' "
                f"cannot exceed 100%."
            )

        if not trigger:
            errors.append(
                f"Product '{name}' version '{version}' fee '{fee_name}' "
                f"must define a trigger."
            )

    for fee_name, items in fee_names.items():
        if len(items) > 1:
            errors.append(
                f"Product '{name}' version '{version}' contains duplicate "
                f"fee name '{fee_name}'."
            )

    return errors


# REPAYMENT

def _validate_repayment(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)

    repayment = getattr(product, "repayment", None)
    if repayment is None:
        errors.append(
            f"Product '{name}' version '{version}' must define repayment."
        )
        return errors

    repayment_type = _text(getattr(repayment, "type", None)).lower()
    grace = int(getattr(repayment, "grace", 0))

    allowed_types = {"annuity", "linear", "bullet"}

    if repayment_type not in allowed_types:
        errors.append(
            f"Product '{name}' version '{version}' uses unsupported "
            f"repayment type '{repayment_type}'. Allowed: "
            f"{', '.join(sorted(allowed_types))}."
        )

    if grace < 0:
        errors.append(
            f"Product '{name}' version '{version}' grace_period cannot be negative."
        )

    term_max = int(getattr(product, "term_max", 0))
    if grace >= term_max and term_max > 0:
        errors.append(
            f"Product '{name}' version '{version}' grace_period ({grace}) "
            f"must be smaller than maximum term ({term_max})."
        )

    return errors


# SCORING

def _validate_scoring(product) -> list[str]:
    errors = []
    name = _name(product)
    version = _version(product)

    scoring = getattr(product, "scoring", None)
    if scoring is None:
        return errors

    threshold = _number(getattr(scoring, "threshold", 0))

    if threshold < 0:
        errors.append(
            f"Product '{name}' version '{version}' scoring threshold "
            f"cannot be negative."
        )

    eligibility = getattr(product, "eligibility", None)
    if eligibility is not None:
        rules = list(getattr(eligibility, "rules", []) or [])
        weighted_rules = [
            _number(getattr(rule, "weight", 0))
            for rule in rules
            if getattr(rule, "weight", None) is not None
        ]

        if weighted_rules:
            max_score = sum(weighted_rules, Decimal("0"))
            if threshold > max_score:
                errors.append(
                    f"Product '{name}' version '{version}' scoring threshold "
                    f"{threshold} exceeds maximum weighted score {max_score}."
                )

    return errors
