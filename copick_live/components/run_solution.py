import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, State
from copick_live.utils.album_utils import get_catalogs, get_groups, get_names, get_versions, get_solution_args

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
