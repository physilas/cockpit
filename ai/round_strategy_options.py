"""Version-2 round goals include the existing expert as a valid strategy.

Legacy proposals and version-1 player plans remain supported unchanged.
"""
from .briefing import proposals as legacy_proposals,validate_plan as legacy_validate

PLAN_VERSION=2


def proposals(state):
    proposal=legacy_proposals(state)
    proposal['plan_version']=PLAN_VERSION
    automatic=(
        ('Flugweite flexibel halten','Die Flugweite passend zum Wurf und zu sichtbaren Partnerzügen wählen.'),
        ('Ausgewogen helfen','Flugweg, Aufgaben und Reserven je nach Lage gegeneinander abwägen.'),
        ('Situativ zusammenspielen','Auf den Partner reagieren und passende Sonderaktionen gemeinsam nutzen.'),
    )
    for goal,(label,reason) in zip(proposal['goals'],automatic):
        goal['options'].append({'value':None,'label':label,'reason':reason})
        goal['selected']=None
    return proposal


def validate_plan(value,state):
    if isinstance(value,dict) and type(value.get('version')) is int and value['version']==1:
        return legacy_validate(value,state)
    if not isinstance(value,dict) or set(value)!={'version','round','movement_preference','focus','coordination'}:
        raise ValueError('Ungültiger Rundenplan.')
    if type(value['version']) is not int or value['version']!=PLAN_VERSION or type(value['round']) is not int or value['round']!=state['runde']:
        raise ValueError('Dieser Plan gehört nicht zur aktuellen Runde.')
    for goal in proposals(state)['goals']:
        selected=value[goal['key']]
        if not any(type(selected) is type(option['value']) and selected==option['value'] for option in goal['options']):
            raise ValueError('Dieses Ziel ist hier nicht verfügbar.')
    return dict(value)


def is_expert_plan(plan):
    return all(plan[key] is None for key in ('movement_preference','focus','coordination'))
