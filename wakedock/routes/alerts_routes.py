"""
Routes pour la gestion des alertes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from wakedock.controllers.alerts_controller import AlertsController
from wakedock.serializers.alerts_serializers import (
    CreateAlertRequest, UpdateAlertRequest, AlertResponse,
    CreateAlertRuleRequest, UpdateAlertRuleRequest, AlertRuleResponse
)
from wakedock.core.database import get_db
from wakedock.core.auth import get_current_user
from wakedock.models.authentication_models import User

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("/", response_model=List[AlertResponse])
async def get_alerts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer la liste des alertes"""
    controller = AlertsController(db)
    return await controller.get_alerts(skip=skip, limit=limit)

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer une alerte spécifique"""
    controller = AlertsController(db)
    alert = await controller.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerte non trouvée"
        )
    return alert

@router.post("/", response_model=AlertResponse)
async def create_alert(
    alert_data: CreateAlertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Créer une nouvelle alerte"""
    controller = AlertsController(db)
    return await controller.create_alert(alert_data.dict(), current_user.id)

@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    alert_data: UpdateAlertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour une alerte"""
    controller = AlertsController(db)
    alert = await controller.update_alert(alert_id, alert_data.dict(), current_user.id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerte non trouvée"
        )
    return alert

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprimer une alerte"""
    controller = AlertsController(db)
    success = await controller.delete_alert(alert_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerte non trouvée"
        )
    return {"message": "Alerte supprimée avec succès"}

# Routes pour les règles d'alerte
@router.get("/rules/", response_model=List[AlertRuleResponse])
async def get_alert_rules(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer la liste des règles d'alerte"""
    controller = AlertsController(db)
    return await controller.get_alert_rules(skip=skip, limit=limit)

@router.post("/rules/", response_model=AlertRuleResponse)
async def create_alert_rule(
    rule_data: CreateAlertRuleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Créer une nouvelle règle d'alerte"""
    controller = AlertsController(db)
    return await controller.create_alert_rule(rule_data.dict(), current_user.id)

@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    rule_data: UpdateAlertRuleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour une règle d'alerte"""
    controller = AlertsController(db)
    rule = await controller.update_alert_rule(rule_id, rule_data.dict(), current_user.id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Règle d'alerte non trouvée"
        )
    return rule

@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprimer une règle d'alerte"""
    controller = AlertsController(db)
    success = await controller.delete_alert_rule(rule_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Règle d'alerte non trouvée"
        )
    return {"message": "Règle d'alerte supprimée avec succès"}
