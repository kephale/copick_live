import dash_bootstrap_components as dbc
from dash import html, dcc

def layout(album_instance):
    index_data = album_instance.get_index_as_dict()
    catalogs = index_data['catalogs']

    catalog_cards = []
    for catalog in catalogs:
        solution_links = []
        for solution in catalog['solutions']:
            solution_links.append(
                html.Li(
                    dcc.Link(
                        f"{solution['setup']['name']} - {solution['setup']['version']}",
                        href=f"/run-solution/{catalog['name']}/{solution['setup']['group']}/{solution['setup']['name']}/{solution['setup']['version']}"
                    )
                )
            )

        catalog_cards.append(
            dbc.Card(
                [
                    dbc.CardHeader(catalog['name']),
                    dbc.CardBody(
                        [
                            html.H5("Solutions", className="card-title"),
                            html.Ul(solution_links)
                        ]
                    )
                ],
                className="mb-3"
            )
        )

    return html.Div(
        [
            html.H1("Album Index"),
            html.Div(catalog_cards)
        ]
    )
