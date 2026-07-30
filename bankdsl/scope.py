def _workflow_scope(current_obj, obj_ref, attribute):
#current je ProcessStep Prijem
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

# obj.name == "Prijem"
#attr == "next"
#obj_ref.obj_name == "Analiza"

def workflow_steps_scope(obj, attr, obj_ref):
    return _workflow_scope(obj, obj_ref, "steps")
#resavamo ProcessStep.next znaci gledamo steps


def workflow_states_scope(obj, attr, obj_ref):
    return _workflow_scope(obj, obj_ref, "states")
#resavamo on_reject znaci gledamo medju states

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
        "ProcessStep.next": workflow_steps_scope,
        "ProcessStep.on_reject": workflow_states_scope,
        "ProcessStep.on_success": workflow_states_scope,
        "Product.workflow": product_workflow_scope,
    })