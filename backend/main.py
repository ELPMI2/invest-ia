from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Invest IA", version="0.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoanIn(BaseModel):
    principal: float
    annualRate: float = Field(..., ge=0, le=1)
    years: int = Field(..., ge=1, le=35)
    insuranceRate: float = 0.0

class PropertyIn(BaseModel):
    price: float
    notaryRate: float = 0.075
    works: float = 0.0
    furnishing: float = 0.0
    agencyFees: float = 0.0
    isNew: bool = False

class RentIn(BaseModel):
    monthly: float
    vacancyRate: float = 0.06

class ChargesIn(BaseModel):
    monthly: float = 0.0
    taxFonciereAnnual: float = 0.0
    managementRate: float = 0.0

class TaxIn(BaseModel):
    regime: Literal["NU_MICRO", "LMNP_MICRO", "LMNP_REEL_LITE"] = "LMNP_MICRO"
    tmi: float = Field(0.11, ge=0, le=0.6)
    psRate: float = Field(0.172, ge=0, le=0.3)

class SimulateIn(BaseModel):
    property: PropertyIn
    rent: RentIn
    charges: ChargesIn
    loan: LoanIn
    tax: Optional[TaxIn] = TaxIn()

def monthly_payment(principal: float, annual_rate: float, years: int, insurance_rate: float = 0.0):
    r = annual_rate / 12
    n = years * 12
    base = principal / n if r == 0 else (principal * r) / (1 - (1 + r) ** (-n))
    insurance = (principal * insurance_rate) / 12
    return base + insurance

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/simulate")
def simulate(payload: SimulateIn):
    p, r_, c, l, tax = payload.property, payload.rent, payload.charges, payload.loan, payload.tax or TaxIn()

    notary = p.price * (0.025 if p.isNew else p.notaryRate)
    total_cost = p.price + notary + p.agencyFees + p.works + p.furnishing

    loyer_brut = r_.monthly * 12
    loyer_annuel = r_.monthly * 12 * (1 - r_.vacancyRate)

    charges_exploit = (c.monthly * 12) + c.taxFonciereAnnual + (c.managementRate * loyer_annuel)
    NOI = loyer_annuel - charges_exploit

    mensualite = monthly_payment(l.principal, l.annualRate, l.years, l.insuranceRate)
    dette_annuelle = mensualite * 12

    interest_y1 = l.principal * l.annualRate
    insurance_annual = l.principal * l.insuranceRate

    cashflow_annuel = loyer_annuel - charges_exploit - dette_annuelle
    cashflow_mensuel = cashflow_annuel / 12

    cap_rate = 0 if total_cost == 0 else NOI / total_cost
    brut = 0 if p.price == 0 else loyer_annuel / p.price
    net_net = 0 if total_cost == 0 else (loyer_annuel - charges_exploit) / total_cost
    dscr = 0 if dette_annuelle == 0 else NOI / dette_annuelle

    tmi, ps = tax.tmi, tax.psRate
    impots_annuels = 0.0
    base_imposable = 0.0
    details_fiscaux = {}

    if tax.regime == "NU_MICRO":
        base_imposable = max(0.0, loyer_annuel * (1 - 0.30))
        impots_annuels = base_imposable * (tmi + ps)
        details_fiscaux = {"abattement": 0.30, "type": "micro-foncier"}
    elif tax.regime == "LMNP_MICRO":
        base_imposable = max(0.0, loyer_annuel * (1 - 0.50))
        impots_annuels = base_imposable * (tmi + ps)
        details_fiscaux = {"abattement": 0.50, "type": "micro-BIC"}
    elif tax.regime == "LMNP_REEL_LITE":
        amort_bien = (p.price * 0.85) / 30.0
        amort_meubles = p.furnishing / 5.0 if p.furnishing else 0.0
        resultat_fiscal = loyer_annuel - (c.monthly * 12) - c.taxFonciereAnnual - (c.managementRate * loyer_annuel) - interest_y1 - insurance_annual - amort_bien - amort_meubles
        base_imposable = max(0.0, resultat_fiscal)
        impots_annuels = base_imposable * (tmi + ps)
        details_fiscaux = {"amort_bien": round(amort_bien, 2), "amort_meubles": round(amort_meubles, 2), "interets_y1": round(interest_y1, 2), "type": "LMNP réel (approx)"}
    else:
        raise HTTPException(status_code=400, detail="Régime fiscal inconnu")

    net_apres_impot_annuel = cashflow_annuel - impots_annuels
    net_apres_impot_mensuel = net_apres_impot_annuel / 12

    return {
        "inputs": payload.model_dump(),
        "results": {
            "totalCost": round(total_cost, 2),
            "loyerBrut": round(loyer_brut, 2),
            "loyerAnnuel": round(loyer_annuel, 2),
            "chargesExploit": round(charges_exploit, 2),
            "NOI": round(NOI, 2),
            "mensualite": round(mensualite, 2),
            "detteAnnuelle": round(dette_annuelle, 2),
            "cashflowMensuel": round(cashflow_mensuel, 2),
            "cashflowAnnuel": round(cashflow_annuel, 2),
            "capRate": round(cap_rate, 4),
            "brut": round(brut, 4),
            "netNet": round(net_net, 4),
            "DSCR": round(dscr, 3),
            "tax": {
                "regime": tax.regime,
                "tmi": tmi,
                "psRate": ps,
                "baseImposable": round(base_imposable, 2),
                "impotsAnnuels": round(impots_annuels, 2),
                "details": details_fiscaux
            },
            "netApresImpotsMensuel": round(net_apres_impot_mensuel, 2),
            "netApresImpotsAnnuel": round(net_apres_impot_annuel, 2)
        }
    }
