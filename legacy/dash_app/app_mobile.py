from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
    "Amount": [4, 1, 2, 2, 4, 5],
    "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"]
})

test_plot_a =  px.bar(df, x="Fruit", y="Amount", color="City", barmode="group")

test_plot_b =  px.bar(df, x="Fruit", y="Amount", color="City", barmode="group")


# Initialize the Dash app

app = Dash(__name__)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='TITLE',
    suppress_callback_exceptions=True,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1, minimum-scale=0.5, maximum-scale=1.2"
    }],
)

app.layout = dbc.Container(
    [
        dbc.Row(
            id='full_page',
            children=[
                dbc.Col(
                    id='sidebar',
                    xs=dict(order=1, size=12),
                    sm=dict(order=1, size=2),
                    style={"border":"2px black solid"},
                    children=["THIS IS THE SIDEBAR"]
                ),
                dbc.Col(
                    id='dash_data',
                    xs=dict(order=2, size=12),
                    sm=dict(order=2, size=10),
                    style={"border":"2px black solid"},
                    children=[
                        dbc.Row(
                            id='comparison_plots',
                            children=[
                                dbc.Col(
                                    
                                    children=[
                                        dcc.Graph(
                                            figure=test_plot_a,
                                            id='pair_plot',
                                        )
                                    ],
                                    style={"border":"2px black solid"},
                                    xs=dict(order=3, size=12),
                                    sm=dict(order=3, size=6),
                                ),
                                dbc.Col(
                                    children=[
                                        dcc.Graph(
                                            figure=test_plot_b,
                                            id='scatter_plot'
                                        )
                                    ],
                                    style={"border":"2px black solid"},
                                    xs=dict(order=4, size=12),
                                    sm=dict(order=4, size=6),
                                )
                            ]
                        ),
                        dbc.Row(
                            id='single_product_plots',
                            children=[
                                dbc.Col(
                                    id='selected_product_title',
                                    children=[dbc.Placeholder(lg=6)],
                                    width=3
                                ),
                                dbc.Col(
                                    id='selected_product_dd',
                                    children=[dbc.Placeholder(lg=6,)],
                                    width=3
                                ),
                                 dbc.Col(
                                    id='selected_product_placeholder',
                                    children=[],
                                    width=6
                                ),
                            ]
                        ),
                        dbc.Row(
                            id='product_details',
                            children=[
                                dbc.Col(
                                    children=[
                                        dcc.Graph(
                                            figure=test_plot_b,
                                        )
                                    ],
                                    width=4
                                ),
                                dbc.Col(
                                    children=[
                                        dcc.Graph(
                                            figure=test_plot_b,
                                        )
                                    ],
                                    width=4
                                ),
                                dbc.Col(
                                    children=[
                                        dcc.Graph(
                                            figure=test_plot_b,
                                        )
                                    ],
                                    width=4
                                ),
                            ]
                        )
                    ]
                )
            ]
        )

    ],fluid=True,
   
)



# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
