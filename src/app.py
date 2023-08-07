from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

# Initialize the Dash app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SLATE],
    suppress_callback_exceptions=True
)

sidebar_text = [
    html.H3("Title placeholder"),
    html.P([
        html.Br(),
        """
            Short description of data collection and mini to standard ratio
        """,
        html.Br(),
        html.Br(),
        """
            tiktok credit
        """,
        html.A("user _____", href="www.google.com"),
        html.Br(),
        html.Br(),
        html.A("link to github", href="https://github.com/leblanchannah/value-cluster")
    ])
]

##### Plotly figures 
def unit_price_pair_plot(df):
    '''
    Returns:
        plotly figure
    '''
    
    fig = px.line(
                df,
                y="value",
                x="variable",
                width=20,
                color="prod_rank",
                title="Unit price comparison of Sephora product size options",
                template="simple_white",
                hover_data={
                    "brand_name":True,
                    "product_name":True,
                    "amount_adj_mini":True,
                    "amount_adj_standard":True,
                    "mini_to_standard_ratio":True,
                    "prod_rank":False,
                },
                markers=True
    )

    fig.update_layout(
        # margin = dict(l=120, r=120), #t=100, b=100),
        yaxis = dict(
            title='Unit price ($/oz.)'
        ),
        xaxis = dict(
            title='Product size',
            type='category',
            tickmode='array',
            tickvals=['unit_price_mini', 'unit_price_standard'],
            ticktext=['Mini','Full'],
            range=[-0.5, 2 - 0.5]
        ),
        hoverlabel = dict(
        # option to change text in hoverlabel
        )
    )
    legend_name_map = {row['prod_rank']:row['display_name'] for index, row in df.iterrows()}
    fig.for_each_trace(lambda t: t.update(name = legend_name_map[int(t.name)]))
    fig.update_traces(line=dict(width=3))


    return fig 


def filter_product_comparison_data(df, col, asc=True, lim=10):
    '''
    '''
    return df.sort_values(by=col, ascending=asc).head(lim)

##### Data
# product data, aggregated to single row per product  
df = pd.read_csv('../data/agg_prod_data.csv')

# for each product, compare all mini size to standard using cross join
df_compare = df[df['swatch_group']=='mini size'].merge(
    df[df['swatch_group']=='standard size'],
    on=['product_id','product_name','brand_name'],
    suffixes=('_mini','_standard')
)
# only calculate ratio in one direction 
df_compare = df_compare[df_compare['amount_adj_mini']<df_compare['amount_adj_standard']]
# if ratio < 1, mini is better value per oz, if ratio > 1, standard is better value
df_compare['mini_to_standard_ratio'] = df_compare['unit_price_mini'] / df_compare['unit_price_standard']

df_compare = filter_product_comparison_data(df_compare, 'mini_to_standard_ratio', asc=True, lim=10)
df_compare = df_compare.reset_index().rename(columns={'index':'prod_rank'})
df_compare = df_compare.melt(['product_id','brand_name','product_name',
                              'prod_rank','amount_adj_mini', 'amount_adj_standard',
                              'mini_to_standard_ratio'])
df_compare = df_compare[df_compare['variable'].isin(['unit_price_mini','unit_price_standard'])]
df_compare = df_compare.merge(df, 
                 on=['product_id','brand_name','product_name'],
                 how='left')
df_compare['display_name'] = df_compare['brand_name']+", "+df_compare['lvl_2_cat'].str.lower()

###### App 
app.layout = dbc.Container([
    html.Br(),
    dbc.Row([
        # side panel col, with title, description etc 
        dbc.Col([
            dbc.Card(
                dbc.CardBody(sidebar_text)
            )
        ], width=2),
        # data viz col
        dbc.Col([
            # explanatory
            dbc.Row([
                # pair plot (mini vs standard)
                dbc.Col([
                    dbc.Card(
                        dbc.CardBody([
                            dcc.Graph(
                                id='pt_plot',
                                figure=unit_price_pair_plot(df_compare)
                            )
                        ])
                    )
                ], width=8),
                # placeholder for now...
                dbc.Col([
                    dbc.Card(dbc.CardBody([]))
                ], width=4)
            ]),
            html.Br(),
            # exploratory
            dbc.Row([
                dbc.Col([
                    dbc.Card(dbc.CardBody([]))
                ], width=12)
            ])
        ], width=10)
    ]),
    html.Br()
], fluid=True)




# df = pd.read_csv('../data/agg_prod_data.csv')

 
# # for each product, compare all mini size to standard using cross join
# df_compare = df[df['swatch_group']=='mini size'].merge(
#     df[df['swatch_group']=='standard size'],
#     on=['product_id','product_name','brand_name'],
#     suffixes=('_mini','_standard')
# )
# # only calculate ratio in one direction 
# df_compare = df_compare[df_compare['amount_adj_mini']<df_compare['amount_adj_standard']]
# # if ratio < 1, mini is better value per oz, if ratio > 1, standard is better value
# df_compare['mini_to_standard_ratio'] = df_compare['unit_price_mini'] / df_compare['unit_price_standard']

# fig_hist = px.histogram(df_compare, x="mini_to_standard_ratio")
# # sort by ratio, best value mini
# df_compare = filter_product_comparison_data(df_compare, 'mini_to_standard_ratio', asc=True, lim=10)
# df_compare = df_compare.reset_index()
# df_compare = df_compare.melt(['product_id','brand_name','product_name','index','amount_adj_mini'])
# df_compare = df_compare[df_compare['variable'].isin(['unit_price_mini','unit_price_standard'])]
# print(df_compare)

# # add tooltip
# # fix axis labels and ticks
# # fix spacing
# # fix line labels
# fig = px.line(
#                 df_compare,
#                 y="value",
#                 x="variable",
#                 color="index",
#                 template="simple_white",
#                 markers=True
#                 )

# fig.update_xaxes({'autorange': False})

# dropdown_options = {x:x for x in df['lvl_0_cat'].unique() if x!=' '}


# # Initialize the Dash app
# app = Dash(__name__, external_stylesheets=[dbc.themes.LUX], suppress_callback_exceptions=True)
# # Define the layout of the app\
# app.layout = html.Div([
#     # Header section
#     dbc.Row([
#         html.H1('Sephora Savings Visualizer'),
#         html.H3('subtitle.'),
#     ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2'}),
#     dbc.Row([
#         dbc.Row([
#             dbc.Col([
#                 dcc.Input(id='range', type='number', min=5, max=20, step=5)
#             ], width=3)
#         ]),
#         dbc.Row([
#             dbc.Col([
#                 html.Div([
#                     dcc.Graph(
#                         id='pt_plot',
#                         figure=fig)
#                     ]),
#                 ], width=6),
#             dbc.Col([
#                 html.Div([
#                     dcc.Graph(
#                         id='ratio_unit_price_hist',
#                         figure=fig_hist
#                     )
#                 ]),
#             ], width=6)
#         ])
#     ]),
        
    
#     # First div with the scatterplot and filters
#     dbc.Row([
#         dbc.Col([
#         dcc.Dropdown(
#             options=dropdown_options,
#             value=next(iter(dropdown_options)),
#             id='crossfilter-dataframe',
#             ),
#         dcc.Graph(
#             id='scatterplot',
#             figure=px.scatter(
#                 df,
#                 x='amount_a',
#                 y='price',
#                 color='swatch_group',
#                 hover_data=['brand_name', 'product_name'],
#                 labels={ # replaces default labels by column name
#                     'amount_a': "Product Size (oz*)",  'price': "Price (CAD)", "swatch_group": "Size Category"
#                 },
#                 template="simple_white"
#             ),
#         ),
#         # Add filters or any other controls here
#         # For example: dcc.Dropdown, dcc.RangeSlider, etc.
#     ], style={'padding': '20px'})])

# ])
# @callback(
#     Output('scatterplot', 'figure'),
#     Input('crossfilter-dataframe', 'value'))
# def update_graph(value):
#     dff = df[df['lvl_0_cat'] == value]

    
#     fig = px.scatter(
#         dff,
#         x='amount_a',
#         y='price',
#         color='swatch_group',
#         hover_data=['brand_name', 'product_name'],
#         labels={ # replaces default labels by column name
#             'amount_a': "Product Size (oz.)*",  'price': "Price (CAD)", "swatch_group": "Size Category"
#         },
#         template="simple_white")
#     return fig


# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
