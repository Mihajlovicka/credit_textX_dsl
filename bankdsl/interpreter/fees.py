"""
Modul za obračun bankarskih naknada (fees).
"""

def calculate_fees(product, principal, n_months):
    result = {
        "processing_fee": 0,
        "processing_rate": 0,
        "monthly_insurance_fee": 0,
        "insurance_rate": 0,
        "early_repayment_fee_rate": 0,
        "total_processing": 0,
        "estimated_total_insurance": 0,
        "estimated_total_fees": 0,
        "estimated_total_interest": 0,
        "total_cost": 0
    }
    
    if not hasattr(product, 'fees') or not product.fees:
        return result
    
    fee_list = product.fees.fees if hasattr(product.fees, 'fees') else []
    for fee in fee_list:
        fee_rate = fee.percent / 100.0
        
        if fee.trigger == "disbursement":
            processing_fee = principal * fee_rate
            result["processing_fee"] = processing_fee
            result["processing_rate"] = fee.percent
            result["total_processing"] = processing_fee
        
        elif fee.trigger == "outstanding_balance" and hasattr(fee, 'freq') and fee.freq == "monthly":
            monthly_insurance = principal * fee_rate
            result["monthly_insurance_fee"] = monthly_insurance
            result["insurance_rate"] = fee.percent
            
            # Prosečan preostali dug je ~polovina glavnice
            avg_balance = principal / 2
            estimated_total = avg_balance * fee_rate * n_months
            result["estimated_total_insurance"] = estimated_total
        
        elif fee.trigger == "early_repayment":
            result["early_repayment_fee_rate"] = fee.percent
    
    result["estimated_total_fees"] = result["total_processing"] + result["estimated_total_insurance"]
    
    if hasattr(product, 'interest'):
        annual_rate = product.interest.rate / 100.0
        monthly_rate = annual_rate / 12
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** n_months) / ((1 + monthly_rate) ** n_months - 1)
        total_paid = monthly_payment * n_months
        result["estimated_total_interest"] = total_paid - principal
    
    result["total_cost"] = principal + result["estimated_total_interest"] + result["estimated_total_fees"]
    
    return result


def calculate_monthly_insurance(outstanding_balance, insurance_rate):
    return outstanding_balance * (insurance_rate / 100.0)