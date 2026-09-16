"""
Funkcije za obračun anuitetske rate i amortizacionog plana.
"""
from bankdsl.interpreter.fees import calculate_fees, calculate_monthly_insurance

def monthly_installment(principal, annual_rate_percent, n_months):
    r = (annual_rate_percent / 100) / 12
    if r == 0:
        return principal / n_months
    return principal * r / (1 - (1 + r) ** (-n_months))


def amortization_schedule(product, principal, n_months=None):
    n_months = n_months or product.term_min
    annual_rate = product.interest.rate
    grace = product.repayment.grace
    r = (annual_rate / 100) / 12

    fees_data = calculate_fees(product, principal, n_months)
    
    insurance_rate = 0
    if hasattr(product, 'fees') and product.fees:
        fee_list = product.fees.fees if hasattr(product.fees, 'fees') else []
        for fee in fee_list:
            if fee.trigger == "outstanding_balance" and hasattr(fee, 'freq') and fee.freq == "monthly":
                insurance_rate = fee.percent
                break

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
        
        # Obračun mesečne naknade osiguranja (na trenutni balance pre otplate)
        current_balance = balance + principal_payment
        insurance_fee = calculate_monthly_insurance(current_balance, insurance_rate)
        total_payment = payment + insurance_fee
        
        schedule.append({
            "month": month,
            "payment": round(payment, 2),
            "interest": round(interest_payment, 2),
            "principal": round(principal_payment, 2),
            "balance": round(balance, 2),
            "insurance_fee": round(insurance_fee, 2),
            "total_payment": round(total_payment, 2),
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
        "fees": fees_data,
    }