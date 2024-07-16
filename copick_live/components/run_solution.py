import dash_bootstrap_components as dbc
from dash import html, dcc

def layout(album_instance):
    return html.Div([
        html.H1("Run Solution"),
        dbc.Form([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Catalog"),
                    dcc.Input(id="catalog-input", type="text", placeholder="Enter catalog name"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Group"),
                    dcc.Input(id="group-input", type="text", placeholder="Enter group name"),
                ], width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Name"),
                    dcc.Input(id="name-input", type="text", placeholder="Enter solution name"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Version"),
                    dcc.Input(id="version-input", type="text", placeholder="Enter version"),
                ], width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Arguments"),
                    dcc.Textarea(id="args-input", placeholder="Enter arguments (one per line)"),
                ], width=12),
            ]),
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
                ], width=6),
                dbc.Col([
                    html.Div(id="submit-slurm-output", className="mt-3"),
                ], width=6),
            ]),
        ]),
        html.Hr(),
        html.H2("SLURM Job Configuration"),
        dbc.Form([
            dbc.Row([
                dbc.Col([
                    dbc.Label("GPUs"),
                    dcc.Input(id="gpus-input", type="number", placeholder="Number of GPUs", value=1),
                ], width=4),
                dbc.Col([
                    dbc.Label("CPUs"),
                    dcc.Input(id="cpus-input", type="number", placeholder="Number of CPUs", value=1),
                ], width=4),
                dbc.Col([
                    dbc.Label("Memory"),
                    dcc.Input(id="memory-input", type="text", placeholder="Memory (e.g., 4G)", value="4G"),
                ], width=4),
            ]),
        ]),
    ])
