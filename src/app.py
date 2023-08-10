from dash import Dash, html, dcc, Input, Output, callback, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

PLOT_TEMPLATE_THEME = 'simple_white'

# product data, aggregated to single row per product  
df = pd.read_csv('../data/agg_prod_data.csv')

# Initialize the Dash app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.MINTY],
    title='Sephora Product Analysis',
    suppress_callback_exceptions=True
)

sidebar_text = html.P([
        html.Br(),
        """
            Comparison of products at Sephora by value, product type, and brand.
        """,
        html.Br(),
        """
            This dashboard is inspired by Tiktok user
        """,
        html.A("@michaelamakeup02's", href="https://www.tiktok.com/@michaelamakeup92/video/7237211338618047787"),
        """
            "Sephora Minis Math" video. 
        """,
        html.Br(),
        # """
        #     Data collected from Sephora on ______. 
        # """,
        html.Br(),
        html.A("github", href="https://github.com/leblanchannah/value-cluster"),
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
                        options = [x for x in df.brand_name.unique()],
                        id='brand_dropdown'
                    )
product_category_l0_global = dcc.Dropdown(
                                options = [x for x in df.lvl_0_cat.unique() if x!=' ' and x!='Mini Size' and x!='Men'],
                                id='category_l0_dropdown'
                            )

@callback(
    Output('scatter_products', 'figure'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    prevent_initial_call=True)
def update_product_scatter(category_val, brand_val):
    triggered_id = ctx.triggered_id 
    df_filtered = df.copy()
    title = f'Explore{" "+brand_val if brand_val else ""}{" "+category_val.lower() if category_val else ""} products by size and price'
    if category_val:
        df_filtered = df_filtered[df_filtered['lvl_0_cat']==category_val]
    if brand_val:
        df_filtered = df_filtered[df_filtered['brand_name']==brand_val]
    return product_unit_price_v_size_scatter(df_filtered, title)


##### Plotly figures and callbacks
def product_unit_price_v_size_scatter(df, title='Explore products by size and price'):
    fig = px.scatter(
                    df,
                    x='amount_adj',
                    y='price',
                    color='swatch_group',
                    title=title,
                    template=PLOT_TEMPLATE_THEME,
                    hover_data=['brand_name', 'product_name'],
                    labels={ # replaces default labels by column name
                        'amount_adj': "Product size (oz.)",  'price': "Price ($)", "swatch_group": "Product category"
                    },
    )
    fig.update_layout(
        legend=dict(
            yanchor='top',
            xanchor='right'
        )
    )
    return fig

@callback(
    Output('size_line_plot', 'figure'),
    Input('sorting_dropdown', 'value'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'))
def update_unit_price_pair_plot(sort_val, category_val, brand_val):
    df_filtered = df.copy()
    title = f'Unit price comparison of{" "+brand_val if brand_val else ""}{" "+category_val.lower() if category_val else ""} products'
    if category_val:
        df_filtered = df_filtered[df_filtered['lvl_0_cat']==category_val]
    if brand_val:
        df_filtered = df_filtered[df_filtered['brand_name']==brand_val]
    return unit_price_pair_plot(get_unit_price_comparison_data(df_filtered, sort_val), title)


def unit_price_pair_plot(df, title="Unit price comparison of products"):
    '''
    Returns:
        plotly figure
    '''
    fig = px.line(
                df,
                y="value",
                x="variable",
                color="prod_rank",
                title=title,
                template=PLOT_TEMPLATE_THEME,
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
        legend=dict(
            title="Top 10 products",
            font_size=12
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


def unit_price_histogram(df, poi_unit_price, unit_price_col):
    '''
    '''
    fig = px.histogram(
            df,
            x=unit_price_col,
            template=PLOT_TEMPLATE_THEME,
            height=300,
            
        )
    return fig


def single_product_info_box(df_poi):

    cheaper = df[(df['unit_price']<df_poi['unit_price'].values[0]) 
                 & (df['amount_adj']==df_poi['amount_adj'].values[0])].shape[0]
    #df.loc[(df.product_name=='soleil brulant') & (df['amount_adj']==1.0)

    return [
        html.H5('Product details'),
        f"Product: {df_poi['product_name'].values[0]}, {df_poi['swatch_group'].values[0]}",
        html.Br(),
        f"Brand: {df_poi['brand_name'].values[0]}",
        html.Br(),
        f"Price: ${df_poi['price'].values[0]}",
        html.Br(),
        f"Size: {df_poi['amount_adj'].values[0]} {df_poi['unit_a'].values[0]}", 
        html.Br(),
        # f"Unit price: {df_poi['unit_price'].values[0]} $/{df_poi['unit_a'].values[0]}",
        html.Br(),
        f"There are {cheaper} {df_poi['amount_adj'].values[0]} {df_poi['unit_a'].values[0]} {df_poi['lvl_2_cat'].values[0].lower()} products at Sephora with unit price less than {df_poi['unit_price'].values[0]} $/{df_poi['unit_a'].values[0]}"
        # str(df['amount_adj'].values[0]),# +" "+ df['unit_a'].values[0],
        # str(df['unit_price'].values[0]),# +" $/"+ df['unit_a'].values[0],
        # str(df['rating'].values[0]),
        # str(df['product_reviews'].values[0]),
        # str(df['sku'].values[0])
    ]


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
    #df_compare['brand_name']+", <br>"+df_compare['lvl_2_cat'].str.lower()
    return df_compare

###### App 
app.layout = dbc.Container([
        html.Br(),
        dbc.Row([
            # side panel col, with title, description etc 
            dbc.Col([
                dbc.Card(
                    dbc.CardBody([
                        html.H3("Sephora product analysis"),
                        sidebar_text,
                        html.H4("Sort by:"),
                        sorting_dropdown,
                        html.Br(),
                        html.H4("Filters:"),
                        "Product category: ",
                        product_category_l0_global,
                        html.Br(),
                        "Brand: ",
                        brand_filter_global,
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
                html.Br(),
                dbc.Row([
                    dbc.Col([
                         dbc.Card(
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col(
                                        single_product_info_box(df[(df.product_name=='soleil brulant') & (df['amount_adj']==1.0)]),
                                        width=3),
                                    dbc.Col([
                                        dcc.Graph(
                                            id='unit_price_hist_plot',
                                            figure=unit_price_histogram(df[(df['amount_adj']==1.0) & (df['lvl_2_cat']=='Perfume')], 310, 'unit_price')
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        '''datatable for recs'''
                                    ], width=3),
                                ])
                            ]))
                    ],width=12)

                ])
            ], width=9)
        ]),
        html.Br(),
        html.Br()
], fluid=True)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
