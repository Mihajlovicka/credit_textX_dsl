"""
Interpreter eligibility pravila iz DSL modela.

Podrzava dva rezima:
  - binarni:  svaki 'require' MORA biti tacan -> APPROVED / REJECTED
  - skoring:  ako proizvod ima 'scoring' blok, racuna se tezinski skor
              i poredi se sa 'threshold'.
"""
import operator as op

OPS = {
    ">=": op.ge, "<=": op.le, "==": op.eq,
    "!=": op.ne, ">": op.gt, "<": op.lt,
}


def _check_rule(rule, application):
    actual = application.get(rule.field)
    if actual is None:
        return False, actual
    try:
        passed = OPS[rule.op](actual, rule.value)
    except TypeError:
        passed = False
    return passed, actual


def check_amount_and_term(product, application):
    problems = []
    if not (product.amount_min <= application.requested_amount <= product.amount_max):
        problems.append(
            f"Trazeni iznos {application.requested_amount} nije u opsegu "
            f"[{product.amount_min}, {product.amount_max}] {product.currency}."
        )
    if not (product.term_min <= application.requested_term <= product.term_max):
        problems.append(
            f"Trazeni rok {application.requested_term} meseci nije u opsegu "
            f"[{product.term_min}, {product.term_max}] meseci."
        )
    return problems


def evaluate_binary(product, application):
    results = []
    all_passed = True
    for rule in product.eligibility.rules:
        passed, actual = _check_rule(rule, application)
        all_passed = all_passed and passed
        results.append({
            "field": rule.field, "operator": rule.op, "expected": rule.value,
            "actual": actual, "passed": passed,
        })

    range_problems = check_amount_and_term(product, application)
    decision = "ODOBREN" if (all_passed and not range_problems) else "ODBIJEN"

    explanation = []
    for r in results:
        status = "OK" if r["passed"] else "NIJE ISPUNJENO"
        explanation.append(
            f"[{status}] {r['field']} {r['operator']} {r['expected']!r} "
            f"(stvarna vrednost: {r['actual']!r})"
        )
    explanation.extend(range_problems)

    return {
        "mode": "binary", "product": product.name, "version": product.version,
        "applicant": application.applicant_name, "decision": decision,
        "rules": results, "explanation": explanation,
    }


def evaluate_scoring(product, application):
    if product.scoring is None:
        raise ValueError(f"Proizvod {product.name} v{product.version} nema definisan scoring blok.")

    results = []
    total_weight = 0.0
    earned_weight = 0.0
    for rule in product.eligibility.rules:
        weight = rule.weight if rule.weight else 1.0
        passed, actual = _check_rule(rule, application)
        total_weight += weight
        if passed:
            earned_weight += weight
        results.append({
            "field": rule.field, "operator": rule.op, "expected": rule.value,
            "actual": actual, "passed": passed, "weight": weight,
        })

    score = (earned_weight / total_weight * 100) if total_weight else 0
    range_problems = check_amount_and_term(product, application)
    decision = "ODOBREN" if (score >= product.scoring.threshold and not range_problems) else "ODBIJEN"

    explanation = [f"Ukupan skor: {score:.1f} / 100 (prag za odobrenje: {product.scoring.threshold})"]
    for r in results:
        status = "OK" if r["passed"] else "NIJE ISPUNJENO"
        explanation.append(
            f"[{status}] (tezina {r['weight']}) {r['field']} {r['operator']} {r['expected']!r} "
            f"(stvarna vrednost: {r['actual']!r})"
        )
    explanation.extend(range_problems)

    return {
        "mode": "scoring", "product": product.name, "version": product.version,
        "applicant": application.applicant_name, "decision": decision,
        "score": round(score, 1), "threshold": product.scoring.threshold,
        "rules": results, "explanation": explanation,
    }


def evaluate(product, application):
    if product.scoring is not None:
        return evaluate_scoring(product, application)
    return evaluate_binary(product, application)
