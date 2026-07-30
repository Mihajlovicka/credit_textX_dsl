# DSL jezik za modelovanje bankarskih kreditnih proizvoda

DSL omogućava korisniku/administratoru da definiše kreditne proizvode, njihove verzije, uslove odobravanja, kamate, naknade, način otplate i kriterijume za skoring, kao i uloge i workflow procesa odobravanja.

```
// ================================================================
// ULOGE
// ================================================================

role KreditniReferent {
    description: "Prima i unosi zahteve klijenata"

    permissions: [
        submit_application,
        view_decision
    ]
}

role KreditniAnalitičar {
    description: "Proverava dokumentaciju i skoring"

    permissions: [
        review_application,
        request_documents
    ]
}

role Odobravalac {
    description: "Donosi konacnu odluku"

    permissions: [
        approve,
        reject
    ]
}


// ================================================================
// WORKFLOW - verzija 1.0
// ================================================================

workflow StandardnoOdobravanje version "1.0" {

    step Prijem {
        handled_by: KreditniReferent
        action: submit_application
        next: Analiza
    }

    step Analiza {
        handled_by: KreditniAnalitičar
        action: review_application
        on_reject: Odbijeno
        next: Odluka
    }

    step Odluka {
        handled_by: Odobravalac
        action: approve
        on_reject: Odbijeno
        on_success: Odobreno
    }

    state Odobreno
    state Odbijeno
}


// ================================================================
// WORKFLOW - verzija 1.1
// ================================================================

workflow StandardnoOdobravanje version "1.1" {

    step Prijem {
        handled_by: KreditniReferent
        action: submit_application
        next: Analiza
    }

    step Analiza {
        handled_by: KreditniAnalitičar
        action: review_application
        on_reject: Odbijeno
        next: Odluka
    }

    step Odluka {
        handled_by: Odobravalac
        action: approve
        on_reject: Odbijeno
        on_success: Odobreno
    }

    state Odobreno
    state Odbijeno
}


// ================================================================
// PROIZVOD - verzija 1.0
// ================================================================

product StambeniKredit version "1.0" {

    type: housing

    valid_from: "2024-01-01"
    valid_to: "2026-06-30"

    amount from 10000 to 100000 EUR
    term from 60 to 360 months

    workflow: StandardnoOdobravanje version "1.0"

    interest {
        type: variable
        rate: 3.5%
        reference: EURIBOR
    }

    eligibility {
        require age >= 18 weight 5
        require age <= 65 weight 5
        require monthly_income >= 500 weight 10
        require employment_status == "permanent" weight 10
        require employment_months >= 12 weight 8
        require credit_score > 650 weight 15
        require loan_to_value_ratio < 0.8 weight 12
        require debt_to_income_ratio < 0.4 weight 15
        require client_type == "individual" weight 5
    }

    fees {
        processing: 1.5% on disbursement
        insurance: 0.3% on outstanding_balance frequency monthly
        early_repayment: 2.0% on early_repayment
    }

    repayment {
        type: annuity
        grace_period: 0 months
    }

    scoring {
        threshold: 70
    }
}


// ================================================================
// PROIZVOD - verzija 1.1
// ================================================================

product StambeniKredit version "1.1" {

    type: housing

    valid_from: "2026-07-01"

    amount from 10000 to 120000 EUR
    term from 60 to 360 months

    workflow: StandardnoOdobravanje version "1.1"

    interest {
        type: variable
        rate: 3.2%
        reference: EURIBOR
    }

    eligibility {
        require age >= 18 weight 5
        require age <= 67 weight 5
        require monthly_income >= 450 weight 10
        require employment_status == "permanent" weight 8
        require employment_months >= 6 weight 6
        require credit_score > 620 weight 15
        require loan_to_value_ratio < 0.85 weight 12
        require debt_to_income_ratio < 0.45 weight 15
        require client_type == "individual" weight 5
    }

    fees {
        processing: 1.2% on disbursement
        insurance: 0.3% on outstanding_balance frequency monthly
        early_repayment: 1.5% on early_repayment
    }

    repayment {
        type: annuity
        grace_period: 3 months
    }

    scoring {
        threshold: 65
    }
}
```

### Predviđene funkcionalnosti

* **Automatsko izračunavanje amortizacionog plana** — na osnovu `interest` i `repayment` bloka izračunava se mesečna rata i generiše puni plan otplate.
* **Scoring/bodovanje** — svakom uslovu se dodeljuje težina, računa se ukupan skor i definiše prag odobrenja.
* **Simulacija „šta ako“** — korisnik menja jedan parametar zahteva i proverava da li bi ta promena uticala na odluku o odobravanju.
* **Verzionisanje proizvoda i workflow-a** — omogućeno je definisanje različitih verzija kreditnog proizvoda i procesa odobravanja.
* **Validacija modela** — sistem proverava konzistentnost definisanih proizvoda, pravila, uloga i workflow-a.
