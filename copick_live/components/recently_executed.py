import dash_bootstrap_components as dbc
from dash import html, dcc, callback
from dash.dependencies import Input, Output, State
from copick_live.utils.album_utils import get_recently_executed_solutions

def create_solution_card(solution):
    return dbc.Card([
        dbc.CardHeader(f"{solution.name} - {solution.version}"),
        dbc.CardBody([
            html.H5(solution.group, className="card-title"),
            html.P(solution.description, className="card-text"),
            dbc.Button("Run Again", href=f"/run-solution/{solution.catalog}/{solution.group}/{solution.name}/{solution.version}", color="primary"),
        ]),
    ], className="mb-3")

def layout():
    return html.Div([
        html.H1("Recently Executed Solutions"),
        dbc.Button("Refresh", id="refresh-recent-solutions", color="primary", className="mb-3"),
        html.Div(id="recent-solutions-container"),
        dcc.Interval(id="refresh-interval", interval=30000, n_intervals=0),  # Refresh every 30 seconds
    ])

@callback(
    Output("recent-solutions-container", "children"),
    [Input("refresh-recent-solutions", "n_clicks"),
     Input("refresh-interval", "n_intervals")],
)
def refresh_recent_solutions(n_clicks, n_intervals):
    solutions = get_recently_executed_solutions()
    return [create_solution_card(solution) for solution in solutions]

def register_callbacks(app, album_instance):
    @app.callback(
        Output("recent-solutions-container", "children"),
        [Input("refresh-recent-solutions", "n_clicks"),
         Input("refresh-interval", "n_intervals")],
        [State("recent-solutions-container", "children")]
    )
    def refresh_recent_solutions(n_clicks, n_intervals, current_children):
        def get_recent_solutions():
            solutions = album_instance.get_collection_index().get_recently_launched_solutions()
            return [s.setup() for s in solutions]

        solutions = get_recent_solutions()
        return html.Div([create_solution_card(solution) for solution in solutions])
