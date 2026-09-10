"""
Amortizacioni kalkulator - iz 'interest' i 'repayment' bloka proizvoda
racuna mesecnu ratu (anuitetska formula) i generise pun plan otplate.
"""


def monthly_installment(principal, annual_rate_percent, n_months):
    """Računa mesečnu anuitetsku ratu."""
    r = (annual_rate_percent / 100) / 12
    if r == 0:
        return principal / n_months
    return principal * r / (1 - (1 + r) ** (-n_months))


def amortization_schedule(product, principal, n_months=None):
    """Generiše kompletan plan amortizacije."""
    n_months = n_months or product.term_min
    annual_rate = product.interest.rate
    grace = product.repayment.grace
    r = (annual_rate / 100) / 12

    schedule = []
    balance = principal
    amortizing_months = n_months - grace
    installment = monthly_installment(principal, annual_rate, amortizing_months)

    for month in range(1, n_months + 1):
        interest_payment = balance * r
        if month <= grace:
            principal_payment = 0.0
            payment = interest_payment
        else:
            payment = installment
            principal_payment = payment - interest_payment
        balance = max(0.0, balance - principal_payment)
        schedule.append({
            "month": month,
            "payment": round(payment, 2),
            "interest": round(interest_payment, 2),
            "principal": round(principal_payment, 2),
            "balance": round(balance, 2),
        })

    return {
        "principal": principal,
        "annual_rate": annual_rate,
        "n_months": n_months,
        "grace_period": grace,
        "regular_installment": round(installment, 2),
        "schedule": schedule,
        "total_paid": round(sum(s["payment"] for s in schedule), 2),
        "total_interest": round(sum(s["interest"] for s in schedule), 2),
    }