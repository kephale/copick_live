import dash_bootstrap_components as dbc
from dash import Dash, html, dcc
from collections import defaultdict

from album.api import Album
from album.runner.core.model.coordinates import Coordinates
from copick_live.components.album_index import layout as album_index
from copick_live.components.run_solution import layout as run_solution_layout
from copick_live.components.recently_executed import layout as recently_executed_layout, register_callbacks as register_recently_executed_callbacks

from copick_live.callbacks.album_callbacks import *

from copick_live.callbacks.update_res import *
from copick_live.components.header import layout as header
from copick_live.components.progress import layout as tomo_progress
from copick_live.components.proteins import layout as protein_sts
from copick_live.components.waitlist import layout as unlabelled_tomos
from copick_live.components.annotators import layout as ranking
from copick_live.components.composition import layout as composition
from copick_live.components.popups import layout as popups


def create_app():
    external_stylesheets = [
        dbc.themes.BOOTSTRAP,
        "assets/header-style.css",
        "https://codepen.io/chriddyp/pen/bWLwgP.css",
        "https://use.fontawesome.com/releases/v5.10.2/css/all.css",
    ]

    app = Dash(__name__, external_stylesheets=external_stylesheets)

    # Initialize Album
    album_instance = Album.Builder().build()
    album_instance.load_or_create_collection()
    
    browser_cache = html.Div(
        id="no-display",
        children=[
            dcc.Interval(
                id="interval-component",
                interval=20 * 1000,  # clientside check in milliseconds, 10s
                n_intervals=0,
            ),
            dcc.Store(id="tomogram-index", data=""),
            dcc.Store(id="keybind-num", data=""),
            dcc.Store(id="run-dt", data=defaultdict(list)),
        ],
    )

    app.layout = html.Div(
        [
            header(),
            popups(),
            dbc.Container(
                [
                    dbc.Row(
                        [
                            # dbc.Col([tomo_progress(), unlabelled_tomos()], width=3),
                            dbc.Col([album_index(album_instance), run_solution_layout(album_instance), recently_executed_layout(album_instance)], width=3),
                            dbc.Col(ranking(), width=3),
                            dbc.Col(composition(), width=3),
                            dbc.Col(protein_sts(), width=3),
                        ],
                        justify="center",
                        className="h-100",
                    ),
                ],
                fluid=True,
            ),
            html.Div(browser_cache),
        ],
    )
    register_recently_executed_callbacks(app, album_instance)
    
    return app


if __name__ == "__main__":
    dash_app = create_app()
    dash_app.run_server(host="0.0.0.0", port=8000, debug=False)
