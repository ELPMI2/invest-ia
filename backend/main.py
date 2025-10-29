from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(title="Invest IA", version="0.2")

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

class RentIn(BaseModel):
    monthly: float
    vacancyRate: float = 0.06

class ChargesIn(BaseModel):
    monthly: float = 0.0
    taxFonciereAnnual: float = 0.0
    managementRate: float = 0.0

class SimulateIn(BaseModel):
    property: PropertyIn
    rent: RentIn
    charges: ChargesIn
    loan: LoanIn
    tax: Optional[dict] = None

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
    p, r, c, l = payload.property, payload.rent, payload.charges, payload.loan

    notary = p.price * p.notaryRate
    total_cost = p.price + notary + p.agencyFees + p.works + p.furnishing

    loyer_annuel = r.monthly * 12 * (1 - r.vacancyRate)
    charges_exploit = (c.monthly * 12) + c.taxFonciereAnnual + (c.managementRate * loyer_annuel)
    NOI = loyer_annuel - charges_exploit

    mensualite = monthly_payment(l.principal, l.annualRate, l.years, l.insuranceRate)
    dette_annuelle = mensualite * 12

    cashflow_annuel = loyer_annuel - charges_exploit - dette_annuelle
    cashflow_mensuel = cashflow_annuel / 12
    cap_rate = 0 if total_cost == 0 else NOI / total_cost
    brut = 0 if p.price == 0 else loyer_annuel / p.price
    net_net = 0 if total_cost == 0 else (loyer_annuel - charges_exploit) / total_cost
    dscr = 0 if dette_annuelle == 0 else NOI / dette_annuelle

    return {
        "inputs": payload.model_dump(),
        "results": {
            "mensualite": round(mensualite, 2),
            "cashflowMensuel": round(cashflow_mensuel, 2),
            "cashflowAnnuel": round(cashflow_annuel, 2),
            "NOI": round(NOI, 2),
            "totalCost": round(total_cost, 2),
            "capRate": round(cap_rate, 4),
            "brut": round(brut, 4),
            "netNet": round(net_net, 4),
            "DSCR": round(dscr, 3)
        }
    }
