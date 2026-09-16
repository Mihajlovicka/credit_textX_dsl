def _workflow_scope(current_obj, obj_ref, attribute):
    # current je ProcessStep Prijem
    workflow = getattr(current_obj, "parent", None)

    while workflow is not None:
        if workflow.__class__.__name__ == "WorkflowDef":
            items = getattr(workflow, attribute, [])

            scope = {
                item.name: item
                for item in items
            }
            return scope.get(obj_ref.obj_name)

        workflow = getattr(workflow, "parent", None)

    return {}

def workflow_states_scope(obj, attr, obj_ref):
    return _workflow_scope(obj, obj_ref, "states")
# resavamo on_reject znaci gledamo medju states


def workflow_node_scope(obj, attr, obj_ref):
    found = _workflow_scope(obj, obj_ref, "steps")
    if found:
        return found
    return _workflow_scope(obj, obj_ref, "states")


def product_workflow_scope(obj, attr, obj_ref):
    model = getattr(obj, "parent", None)
    workflow_version = str(getattr(obj, "workflow_version", "")).strip()

    if model is None:
        return {}

    return {
        workflow.name: workflow
        for workflow in getattr(model, "workflows", [])
        if workflow.version == workflow_version
    }.get(obj_ref.obj_name)


def register_scopes(metamodel):
    metamodel.register_scope_providers({
        "ProcessStep.next": workflow_node_scope,
        "ProcessStep.on_reject": workflow_states_scope,
        "ProcessStep.on_success": workflow_states_scope,
        "Product.workflow": product_workflow_scope,
    })