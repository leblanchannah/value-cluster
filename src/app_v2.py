from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px


df = pd.read_csv('../data/agg_prod_data.csv')
# df_ratios = pd.read_csv('')

# Initialize the Dash app
app = Dash(__name__)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='Sephora Product Analysis'
)

PLOT_TEMPLATE_THEME = 'simple_white'

# FORM components
product_category_l0_dropdown = dbc.Select(
    id='product_category_l0_dropdown',
    options = [x for x in df.lvl_0_cat.unique() if x!=' ' and x!='Mini Size' and x!='Men'],
    value='Makeup'
)

brand_dropdown = dbc.Select(
    id='brand_dropdown',
    options=[x for x in df.brand_name.unique()]

)

ratio_sorting_dropdown = dbc.Select(
    id='ratio_sorting_dropdown',
    options=[]
)


product_options = [{'label':x.product_name+' '+x.brand_name+' '+x.swatch_group,'value':x.index} for x in df[['product_name','brand_name','index','swatch_group']].itertuples()]
product_info_dropdown = dbc.Select(
    id='product_info_dropdown',
    options=product_options,
    placeholder='Dior Forever Loose Cushion Powder',
    value=4168,
    # optionHeight=70,
)

max_price_filter = dbc.Input(
    id='max_price_filter',
    type='number',
    min=0,
    max=2000,
    step=5
)




app.layout = dbc.Container([
    # title
    dbc.Row([
        dbc.Col([
        ], width=12)
    ]),
    # unit price comparison
    dbc.Row([
        dbc.Col([
            # filters 
            dbc.Row([
                # Product type filter
                dbc.Col(
                    id='product_category_filter',
                    children=[
                        dbc.InputGroup([
                            dbc.InputGroupText("Product Type"),
                            product_category_l0_dropdown
                        ])
                    ],
                    width=3
                ),
                # Brand filter
                dbc.Col(
                    id='brand_filter',
                    children=[
                        dbc.InputGroup([
                            dbc.InputGroupText("Brand"),
                            brand_dropdown
                        ])
                    ],
                    width=3
                ),
                # Price filter
                dbc.Col(
                    id='price_filter',
                    children=[
                        dbc.InputGroup([
                            dbc.InputGroupText("Max Price"),
                            max_price_filter

                        ])
                    ],
                    width=3
                ),
                # Ratio selection 
                dbc.Col(
                    id='ratio_sorting',
                    children=[
                        dbc.InputGroup([
                            dbc.InputGroupText("Sort By"),
                            ratio_sorting_dropdown
                        ]),
                    ],
                    width=3
                ),
            ]),
            # figure with 2 subplots 
            dbc.Row([
                dbc.Col([
                    dcc.Graph()
                ], width=12)
            ]),
        ], width=12),
    ]),
    # product details 
    dbc.Row([
        dbc.Col([
            # filters
            dbc.Row([
                dbc.Col([

                ], width=12)
            ]),
            dbc.Row([
                # product details
                dbc.Col([

                ], width=4),
                # unit price histogram
                dbc.Col([
                    dcc.Graph()
                ], width=4),
                # product table
                dbc.Col([
                    dash_table.DataTable(
                        id='product_options',
                        data=None,
                        columns=[
                            {"name": 'Brand', "id": 'brand_name'},
                            {"name": 'Product', "id": 'product_name'},
                            {"name": 'Unit Price ($/oz.)', "id": 'unit_price', 'type':'numeric', 'format':dash_table.Format.Format(precision=2, scheme=dash_table.Format.Scheme.fixed)},
                            {"name": 'Rating', 'id':'rating', 'type':'numeric', 'format':dash_table.Format.Format(precision=1, scheme=dash_table.Format.Scheme.fixed)}
                        ],
                        page_size=8,
                        style_cell={
                            'font-family':'sans-serif',
                            'textAlign': 'left',
                            'fontSize':12,
                            'overflow': 'hidden',
                            'textOverflow': 'ellipsis',
                            'backgroundColor':'white',
                            'lineColor':'black'
                        },
                        style_header={
                            'backgroundColor': '#F8E1F2',
                            'fontWeight': 'bold'
                        },
                        style_data={
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'lineHeight': '15px'
                        },
                        style_table={
                            "overflowX": "auto"
                        }
                    )
                ], width=4)

            ])
        ], width=12)

    ]),
],
fluid=True
)

if __name__ == '__main__':
    app.run_server(debug=True)
