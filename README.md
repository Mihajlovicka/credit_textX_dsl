# BankCreditDSL

## DSL jezik za modelovanje bankarskih kreditnih proizvoda

DSL omogućava korisniku/administratoru da definiše:

* uloge i njihove permisije;
* workflow procese odobravanja;
* verzije workflow-a;
* kreditne proizvode i njihove verzije;
* periode važenja proizvoda;
* dozvoljene iznose i rokove otplate;
* kamatne stope;
* eligibility pravila;
* scoring kriterijume;
* naknade;
* način otplate i grace period.

Zahtev konkretnog klijenta nije deo DSL jezika. Klijentski zahtev se predstavlja posebnim JSON fajlom, odnosno podacima koje bi u realnom sistemu uneo formular ili drugi klijentski sistem.

---

## Funkcionalnosti

Projekat trenutno podržava:

* textX gramatiku za `.credit` fajlove;
* parsiranje DSL modela;
* semantičku validaciju modela;
* razrešavanje referenci između uloga, workflow-a, koraka i proizvoda;
* evaluaciju klijentskog zahteva;
* binary i scoring režim odlučivanja;
* računanje amortizacionog plana;
* workflow procesiranje;
* interaktivno procesiranje workflow-a korak po korak;
* trajno čuvanje procesnog stanja u SQLite bazi;
* generisanje HTML/PDF izveštaja o odluci;
* generisanje CSV i HTML amortizacionog plana;
* generisanje HTML/PDF izveštaja o toku workflow procesa (uloge i koraci);
* registrovanje jezika i generatora u textX-u;
* command-line interfejs `bank-credit`;
* instalaciju projekta preko `pip`;
* editable instalaciju preko `pip install -e .`.

---

# DSL model

Jedan `.credit` fajl može sadržati više uloga, workflow-a i proizvoda.

Osnovni elementi jezika su:

```text
role
workflow
step
state
product
interest
eligibility
fees
repayment
scoring
```

## Uloge

Uloge definišu ko može da izvršava određene akcije u procesu:

```text
role KreditniReferent {
    description: "Prima i unosi zahteve klijenata"

    permissions: [
        submit_application,
        view_decision
    ]
}
```

## Workflow

Workflow definiše proces odobravanja:

```text
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
```

Workflow-i mogu imati više verzija:

```text
workflow StandardnoOdobravanje version "1.0" {
    ...
}

workflow StandardnoOdobravanje version "1.1" {
    ...
}
```

Proizvod eksplicitno određuje koju verziju workflow-a koristi.

## Kreditni proizvod

Primer:

```text
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
```


# Evaluacija klijentskog zahteva

Evaluacija se nalazi u:

```text
bankdsl/interpreter/evaluator.py
```

Podržana su dva režima.

## Scoring

Ako proizvod ima `scoring` blok, svakom eligibility pravilu može biti dodeljena težina.

Sistem računa procenat osvojenih poena i poredi ga sa definisanim `threshold`-om.

Na primer:

```text
scoring {
    threshold: 70
}
```

Ako klijent ispuni pravila koja nose dovoljno poena da dostigne prag, zahtev prolazi scoring proveru.

## Binary režim

Ako proizvod nema `scoring` blok, sva eligibility pravila moraju biti ispunjena.

U oba režima proveravaju se i:

* traženi iznos u odnosu na `amount`;
* traženi rok u odnosu na `term`.

Ako potrebna vrednost ne postoji u JSON zahtevu, odgovarajuće pravilo se smatra neispunjenim.

---

# Amortizacioni plan

Amortizacioni plan se računa u:

```text
bankdsl/interpreter/amortization.py
```

Podržano je:

* godišnja kamatna stopa;
* broj meseci;
* mesečna rata;
* raspodela rate na kamatu i glavnicu;
* preostali dug;
* grace period;
* ukupno plaćeno;
* ukupna kamata.

Za `annuity` način otplate generiše se kompletan mesečni plan.

Naknade iz `fees` bloka su uključene u obračun — mesečna rata u planu sadrži i obračunatu mesečnu naknadu osiguranja (`insurance_fee`, uz `total_payment` kao ukupan mesečni iznos), a jednokratne naknade (`processing`, `early_repayment`) se vraćaju odvojeno kao deo rezultata.
---

# Proces odobravanja

Projekat ima dva načina izvršavanja workflow procesa.

## Pipeline izvršavanje

```text
bankdsl/interpreter/process_engine.py
```

Ovaj modul izvršava kompletan workflow kao jedan procesni tok.

## Interaktivno procesiranje

```text
bankdsl/interpreter/process_session.py
```

Ovaj modul izvršava workflow korak po korak i čuva stanje između poziva u SQLite bazi.

Proces:

1. kreira se proces;
2. proces staje na prvom koraku;
3. odgovarajuća uloga izvršava korak;
4. stanje se čuva;
5. sledeći poziv nastavlja proces;
6. proces se završava kada se dostigne završno stanje.

Procesni motor je generički i ne zavisi od konkretnih naziva uloga ili akcija.

Ako korisnik pokuša da izvrši korak u pogrešnoj ulozi, dobija `PermissionError`, a stanje procesa se ne menja.

Evaluacija odluke se izvršava jednom i rezultat se čuva zajedno sa procesom.

---

# Instalacija

Projekat zahteva:

```text
Python 3.10+
```

## Instalacija iz izvornog koda

Klonirati repozitorijum i ući u njegov direktorijum:

```bash
git clone https://github.com/Mihajlovicka/credit_textX_dsl.git
cd credit_textX_dsl
```

Kreirati i aktivirati virtuelno okruženje:

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

# Instalacija kao paket

Projekat je definisan pomoću `pyproject.toml` i može se instalirati kao standardni Python paket:

```bash
python -m pip install .
```

Nakon instalacije dostupna je komanda:

```bash
bank-credit --help
```

# Provera `.credit` modela

Najjednostavniji način je:

```bash
bank-credit validate examples/stambeni_kredit.credit
```

```bash
python -m bankdsl.cli validate examples/stambeni_kredit.credit
```

---

# TextX CLI

BankCreditDSL je registrovan kao textX jezik.

Jezik se može proveriti pomoću:

```bash
textx list-languages
```

Trebalo bi da se pojavi:

```text
BankCreditDSL
```

Registrovani generatori mogu se proveriti pomoću:

```bash
textx list-generators
```

Generatori su dostupni kroz standardnu textX komandu:

```bash
textx generate
```

Ovo je odvojeno od korisničkog CLI-ja `bank-credit`.

`textx generate` predstavlja standardni textX interfejs za generatore, dok `bank-credit` predstavlja CLI specifičan za ovaj projekat.

---

# Generatori

## Decision report

Generator:

```text
decision-report
```

generiše HTML izveštaj o odluci i pokušava da generiše PDF.

Primer:

```bash
textx generate examples/stambeni_kredit.credit --target decision-report --application examples/aplikacije/marko.json
```

Generator može da se pozove i preko custom CLI-ja:

```bash
bank-credit report examples/stambeni_kredit.credit --application examples/aplikacije/marko.json
```

Izveštaj sadrži informacije o:

* proizvodu;
* verziji proizvoda;
* klijentskom zahtevu;
* rezultatima evaluacije;
* odluci;
* objašnjenju pravila.

Generator izveštaja takođe upisuje podatke o proizvodu, zahtevu i odluci u SQLite bazu.

PDF izlaz koristi `xhtml2pdf`, čistu Python biblioteku instaliranu preko `pip install -e .` — ne zahteva nikakav spoljašnji program. Ako PDF generisanje iz nekog razloga ne uspe, HTML izveštaj se i dalje generiše.
---

# Amortization generator

Generator:

```text
amortization
```

generiše:

* CSV amortizacioni plan;
* HTML amortizacioni plan;
* PDF amortizacioni plan (preko iste `xhtml2pdf` biblioteke).

Primer preko textX CLI-ja:

```bash
textx generate examples/stambeni_kredit.credit --target amortization --application examples/aplikacije/marko.json
```

Isto preko custom CLI-ja:

```bash
bank-credit amortization examples/stambeni_kredit.credit --application examples/aplikacije/marko.json
```

CSV sadrži podatke kao što su:

```text
mesec
rata
kamata
glavnica
preostalo
```

---

# Workflow report generator

Generator:

```text
workflow-report
```

izvršava CEO workflow (uloge, koraci, dozvole) u jednom prolazu i generiše
HTML izveštaj o toku procesa, i pokušava da generiše PDF.

Za razliku od `decision-report` (koji proverava samo eligibility pravila) i
interaktivnog `process` (koji čuva stanje između poziva u bazi), ovaj
generator je jednokratna simulacija celog workflow-a — koristan za brzu
proveru "da li bi ovaj zahtev prošao kroz ceo proces, i preko kojih tačno
koraka i uloga".

Primer preko textX CLI-ja:

```bash
textx generate examples/stambeni_kredit.credit --target workflow-report --application examples/aplikacije/marko.json
```

Isto preko custom CLI-ja:

```bash
bank-credit workflow-report examples/stambeni_kredit.credit --application examples/aplikacije/marko.json
```

Izveštaj sadrži:

* proizvod i verziju workflow-a koji je korišćen;
* konačno stanje (npr. `Odobreno`/`Odbijeno`);
* trag kroz koje je korake zahtev prošao;
* ulogu i akciju izvršenu na svakom koraku;
* obrazloženje odluke (eligibility provera), ako korak predstavlja tačku
  odlučivanja.

PDF izlaz koristi istu `xhtml2pdf` biblioteku kao i `decision-report` i
`amortization` generatori. Ako PDF ne uspe da se generiše, HTML izveštaj se
i dalje pravi.

---

# Interaktivni proces odobravanja

Procesni CLI je deo glavnog `bank-credit` CLI-ja.

## Pokretanje procesa

```bash
bank-credit process start examples/stambeni_kredit.credit --application examples/aplikacije/marko.json
```

Komanda kreira novi proces i zaustavlja ga na prvom koraku.

Primer rezultata:

```text
Proces #1 pokrenut za 'Marko Petrovic'.
Ceka se korak 'Prijem' (uloga: KreditniReferent).
```

## Pregled statusa

```bash
bank-credit process status 1
```

## Izvršavanje koraka

```bash
bank-credit process advance examples/stambeni_kredit.credit 1 --role KreditniReferent
```

Zatim:

```bash
bank-credit process advance examples/stambeni_kredit.credit 1 --role KreditniAnalitičar
```

I na kraju:

```bash
bank-credit process advance examples/stambeni_kredit.credit 1 --role Odobravalac
```

Proces može završiti u stanju:

```text
Odobreno
```

ili:

```text
Odbijeno
```

u zavisnosti od rezultata evaluacije i definisanog workflow-a.

---

# Format klijentskog zahteva

Klijentski zahtev je JSON dokument.

Primer:

```json
{
    "applicant_name": "Marko Petrovic",
    "product_name": "StambeniKredit",
    "product_version": "1.0",
    "requested_amount": 45000,
    "requested_term": 240,
    "data": {
        "age": 34,
        "monthly_income": 650,
        "employment_status": "permanent",
        "employment_months": 48,
        "credit_score": 720,
        "loan_to_value_ratio": 0.65,
        "debt_to_income_ratio": 0.32,
        "client_type": "individual"
    }
}
```

Obavezni podaci su:

* `applicant_name`
* `product_name`
* `product_version`
* `requested_amount`
* `requested_term`

`data` je objekat koji sadrži vrednosti potrebne za evaluaciju eligibility pravila.

Na primer:

```text
require age >= 18
```

se evaluira korišćenjem:

```json
{
    "data": {
        "age": 34
    }
}
```

Verzija proizvoda navedena u zahtevu mora postojati u učitanom `.credit` modelu.

---

# Kompletan primer modela

Primer modela:

```text
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


# Buduća proširenja

Moguća proširenja projekta su:

* simulacija „šta ako“;
* workflow dijagrami;
* podrška za više načina otplate;
* HTTP API;
* web korisnički interfejs;
* zamena SQLite storage-a PostgreSQL bazom;
* dodatni formati izveštaja;
* naprednije scoring funkcije;
* podrška za više valuta i konverziju;
* verzionisanje i migracija DSL modela.

---