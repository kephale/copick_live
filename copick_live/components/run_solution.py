import json
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, State, ALL
from copick_live.utils.album_utils import get_catalogs, get_groups, get_names, get_versions, get_solution_args
from copick_live.celery_tasks import submit_slurm_job

import logging
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

def layout():
    catalogs = get_catalogs()
    
    return html.Div([
        html.H1("Album Solutions"),
        dbc.Form([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Catalog"),
                    dcc.Dropdown(id="catalog-input", options=[{'label': cat['name'], 'value': cat['name']} for cat in catalogs], placeholder="Select catalog"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Group"),
                    dcc.Dropdown(id="group-input", placeholder="Select group"),
                ], width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Name"),
                    dcc.Dropdown(id="name-input", placeholder="Select solution name"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Version"),
                    dcc.Dropdown(id="version-input", placeholder="Select version"),
                ], width=6),
            ]),
            html.Div(id="dynamic-args"),
            dbc.Row([
                dbc.Col([
                    dbc.Button("Run Solution", id="run-solution-button", color="primary", className="mt-3"),
                ], width=6),
                dbc.Col([
                    dbc.Button("Submit SLURM Job", id="submit-slurm-button", color="secondary", className="mt-3"),
                    html.Div(id="submit-slurm-output", className="mt-3"),
                ], width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id="run-solution-output", className="mt-3"),
                ], width=12),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id="submit-slurm-output", className="mt-3"),
                ], width=12),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id="solution-output"),
                ], width=12),
            ]),
            dcc.Store(id='task-id-store'),
            dcc.Interval(id='solution-output-interval', interval=1000, n_intervals=0, disabled=True),
        ]),
    ])

@callback(
    Output("group-input", "options"),
    Input("catalog-input", "value")
)
def update_groups(catalog):
    if not catalog:
        return []
    groups = get_groups(catalog)
    return [{'label': group, 'value': group} for group in groups]

@callback(
    Output("name-input", "options"),
    Input("catalog-input", "value"),
    Input("group-input", "value")
)
def update_names(catalog, group):
    if not catalog or not group:
        return []
    names = get_names(catalog, group)
    return [{'label': name, 'value': name} for name in names]

@callback(
    Output("version-input", "options"),
    Input("catalog-input", "value"),
    Input("group-input", "value"),
    Input("name-input", "value")
)
def update_versions(catalog, group, name):
    if not catalog or not group or not name:
        return []
    versions = get_versions(catalog, group, name)
    return [{'label': version, 'value': version} for version in versions]

@callback(
    Output("dynamic-args", "children"),
    Input("catalog-input", "value"),
    Input("group-input", "value"),
    Input("name-input", "value"),
    Input("version-input", "value")
)
def update_dynamic_args(catalog, group, name, version):
    if not catalog or not group or not name or not version:
        return []
    
    args = get_solution_args(catalog, group, name, version)
    
    arg_inputs = []
    for arg in args:
        arg_inputs.append(dbc.Row([
            dbc.Col([
                dbc.Label(f"{arg['name']} ({arg['type']}){'*' if arg.get('required') else ''}"),
                dcc.Input(id={'type': 'arg-input', 'index': arg['name']}, type="text", placeholder=arg.get('default', ''), className="form-control")
            ], width=12)
        ]))
    return arg_inputs

@callback(
    Output("submit-slurm-output", "children"),
    Input("submit-slurm-button", "n_clicks"),
    State("catalog-input", "value"),
    State("group-input", "value"),
    State("name-input", "value"),
    State("version-input", "value"),
    State({"type": "arg-input", "index": ALL}, "value"),
    State({"type": "arg-input", "index": ALL}, "id"),
    prevent_initial_call=True
)
def submit_slurm(n_clicks, catalog, group, name, version, arg_values, arg_ids):
    if n_clicks:
        args = {}
        for arg_id, arg_value in zip(arg_ids, arg_values):
            if arg_value:
                args[arg_id['index']] = arg_value
        
        logger.info(f"Submitting SLURM job for {catalog}:{group}:{name}:{version}")
        task = submit_slurm_job.delay(catalog, group, name, version, args=json.dumps(args))
        return dcc.Loading(id="loading-submit-slurm", children=[
            html.Div(f"SLURM job submission started with task ID: {task.id}"),
            dcc.Interval(id='slurm-output-interval', interval=1000, n_intervals=0),
            html.Div(id='slurm-status-output'),
            dcc.Store(id='slurm-task-id-store', data=str(task.id))
        ])
    return ""

@callback(
    Output("slurm-status-output", "children"),
    Input("slurm-output-interval", "n_intervals"),
    State("slurm-task-id-store", "data"),
    prevent_initial_call=True
)
def update_slurm_status(n_intervals, task_id):
    if task_id:
        task = submit_slurm_job.AsyncResult(str(task_id))
        logger.info(f"SLURM submission task {task_id} state: {task.state}")
        if task.state == 'PENDING':
            return 'SLURM job submission is pending...'
        elif task.state == 'STARTED':
            return 'SLURM job submission is in progress...'
        elif task.state == 'SUCCESS':
            if task.result:
                return f"SLURM job submitted successfully. Job ID: {task.result.get('slurm_job_id', 'Unknown')}"
            else:
                return 'SLURM job submission completed, but no job ID was returned.'
        elif task.state == 'FAILURE':
            return f'SLURM job submission failed: {str(task.result)}'
        else:
            return f'Unknown SLURM submission task state: {task.state}'
    return ''
