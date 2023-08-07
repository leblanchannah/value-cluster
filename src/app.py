from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

# product data, aggregated to single row per product  
df = pd.read_csv('../data/agg_prod_data.csv')

# Initialize the Dash app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SLATE],
    suppress_callback_exceptions=True
)

sidebar_text = html.P([
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
        html.A("link to github", href="https://github.com/leblanchannah/value-cluster"),
        html.Br(),
        html.Br(),
])

sorting_dropdown = dcc.Dropdown(
                        options=[
                            {'label':'Best mini compared to full size','value':'ratio_mini_lt_full'},
                            {'label':'Best full compared to mini size','value':'ratio_full_lt_mini'},
                            {'label':'Best value mini size','value':'unit_price_mini'},
                            {'label':'Best value full size','value':'unit_price_full'},
                        ],
                        value='ratio_mini_lt_full',
                        id='sorting_dropdown'
                    )

brand_filter_global = dcc.Dropdown(
                        #options = [x for x in df.brand_name.unique()]
                    )
product_category_l0_global = dcc.Dropdown(
                                options = [x for x in df.lvl_0_cat.unique() if x!=' ' and x!='Mini Size' and x!='Men'],
                                id='category_l0'
                            )

@callback(
    Output('scatter_products', 'figure'),
    Input('category_l0', 'value'))
def update_product_unit_price_v_size_scatter(value):
    if not value:
        return product_unit_price_v_size_scatter(df)
    return product_unit_price_v_size_scatter(df[df['lvl_0_cat']==value])

##### Plotly figures and callbacks
def product_unit_price_v_size_scatter(df):
    fig = px.scatter(
                    df,
                    x='amount_adj',
                    y='price',
                    color='swatch_group',
                    hover_data=['brand_name', 'product_name'],
                    labels={ # replaces default labels by column name
                        'amount_adj': "Product size (oz.)",  'price': "Price ($)", "swatch_group": "Product category"
                    },
                    template="simple_white"
    )
    return fig


@callback(
    Output('size_line_plot', 'figure'),
    Input('sorting_dropdown', 'value'))
def update_unit_price_pair_plot(value):
    return unit_price_pair_plot(get_unit_price_comparison_data(df, value))


def unit_price_pair_plot(df):
    '''
    Returns:
        plotly figure
    '''
    fig = px.line(
                df,
                y="value",
                x="variable",
                color="prod_rank",
                title="Unit price comparison of Sephora product size options",
                template='simple_white',
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
        yaxis = dict(
            title='Unit price ($/oz.)'
        ),
        xaxis = dict(
            title='Product size',
            type='category',
            tickmode='array',
            tickvals=['unit_price_mini', 'unit_price_standard'],
            ticktext=['Mini','Full'],
            range=[-0.4, 2 - 0.6]
        ),
        hoverlabel = dict(
        # option to change text in hoverlabel
        )
    )
    # map line index to brand+category label
    legend_name_map = {row['prod_rank']:row['display_name'] for index, row in df.iterrows()}
    fig.for_each_trace(lambda t: t.update(name = legend_name_map[int(t.name)]))
    fig.update_traces(line=dict(width=3))
    return fig 


def basic_df_sort(df, col, asc=True, limit=10):
    return df.sort_values(by=col, ascending=asc).head(limit)


def sort_product_comparison_data(df, dropdown_value, limit=10):
    '''
    '''
    if dropdown_value=='ratio_mini_lt_full':
        return basic_df_sort(df, 'mini_to_standard_ratio', asc=True, limit=limit)
    elif dropdown_value=='ratio_full_lt_mini':
        return basic_df_sort(df, 'mini_to_standard_ratio', asc=False, limit=limit)
    elif dropdown_value=='unit_price_mini':
        return basic_df_sort(df, 'unit_price_mini', asc=True, limit=limit)
    elif dropdown_value=='unit_price_full':
        return basic_df_sort(df, 'unit_price_standard', asc=True, limit=limit)
    else:
        return df
    

def get_unit_price_comparison_data(df, sorting_value='ratio_mini_lt_full'):
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
    df_compare = df_compare.reset_index().rename(columns={'index':'prod_rank'})

    df_compare = sort_product_comparison_data(df_compare, sorting_value)

    df_compare = df_compare.melt(['product_id','brand_name','product_name',
                                'prod_rank','amount_adj_mini', 'amount_adj_standard',
                                'mini_to_standard_ratio'])
    df_compare = df_compare[df_compare['variable'].isin(['unit_price_mini','unit_price_standard'])]
    df_compare = df_compare.merge(df, 
                    on=['product_id','brand_name','product_name'],
                    how='left')
    df_compare['display_name'] = df_compare['brand_name']+", "+df_compare['lvl_2_cat'].str.lower()
    return df_compare

###### App 
app.layout = dbc.Container([
        html.Br(),
        dbc.Row([
            # side panel col, with title, description etc 
            dbc.Col([
                dbc.Card(
                    dbc.CardBody([
                        html.H3("Title placeholder"),
                        sidebar_text,
                        html.H4("Sort by:"),
                        sorting_dropdown,
                        html.Br(),
                        html.H4("Filter:"),
                        product_category_l0_global
                    ])
                )
            ], width=3),
            # data viz col
            dbc.Col([
                # explanatory
                dbc.Row([
                    # pair plot (mini vs standard)
                    dbc.Col([
                        dbc.Card(
                            dbc.CardBody([
                                dcc.Graph(
                                    id='size_line_plot',
                                    figure=unit_price_pair_plot(get_unit_price_comparison_data(df))
                                )
                            ])
                        )
                    ], width=6),
                    # placeholder for now...
                    dbc.Col([
                        dbc.Card(
                            dbc.CardBody([
                                dcc.Graph(
                                    id='scatter_products',
                                    figure=product_unit_price_v_size_scatter(df)
                                )

                            ])
                        )
                    ], width=6),
                    
                ]),
                html.Br()
            ], width=9)
        ]),
        html.Br(),
        html.Br()
], fluid=True)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
