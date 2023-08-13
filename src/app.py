from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table
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


def single_product_info_box(df, data):
    # cheaper products must have better unit price, lower price and same amount

    unit_price = (df['unit_price']<data['unit_price']) 
    l2_type = (df['lvl_2_cat']==data['lvl_2_cat']) 
    num_cheaper_products = df[unit_price & l2_type].shape[0]
    return [
        html.H5('Product details'),
        f"Product: {data['product_name']}, {data['swatch_group']}",
        html.Br(),
        f"Brand: {data['brand_name']}",
        html.Br(),
        f"Price: ${data['price']}",
        html.Br(),
        f"Size: {data['amount_adj']} {data['unit_a']}", 
        html.Br(),
        html.Br(),
        f"There are {num_cheaper_products} {data['lvl_2_cat'].lower()} products at Sephora with unit price less than {data['unit_price']} $/{data['unit_a']}"
    ]


@callback(
    Output('product_details_text', 'children'),
    Output('unit_price_hist_plot', 'figure'),
    Input('scatter_products', 'clickData'),
    Input('size_line_plot', 'clickData'))
def update_product_details(scatter_click_value, slope_click_value):
    # sequential clicks show data in both scatter value and slope value - making it difficult to tell what is most recent
    # print(scatter_click_value)
    # print(slope_click_value)
    # ctx triggered gives most recent and all the same data under customdata key
    click_data = ctx.triggered[0]
    if click_data['value'] is not None:
        # either scatterplot or slope plot has been clicked
        # index must always be last item in custom_data, regardless of what plot it came from 
        product_row_id = click_data['value']['points'][0]['customdata'][-1]
        data = get_single_product_data(df, product_row_id)
        df_filtered = df[df['lvl_2_cat']==data['lvl_2_cat']]
        return single_product_info_box(df, data), unit_price_histogram(df_filtered, 0, 'unit_price')
    return single_product_info_box(df, get_single_product_data(df, 4)), unit_price_histogram(df, 0, 'unit_price')


def unit_price_histogram(data, position_, unit_price_col):
    '''
    '''
    fig = px.histogram(
            data,
            x=unit_price_col,
            template=PLOT_TEMPLATE_THEME,
            height=300,
            
        )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis=dict(
            autorange=True
        ),
        xaxis=dict(
            autorange=True
        )
    )
    return fig


def get_single_product_data(df, row_id, index_col='index'):
    # must return single row of data as dictionary
    return df[df[index_col]==row_id].to_dict('records')[0]


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
                    hover_data=['brand_name', 'product_name', 'index'],
                    labels={ # replaces default labels by column name
                        'amount_adj': "Product size (oz.)",  'price': "Price ($)", "swatch_group": "Product category"
                    },
    )
    fig.update_layout(
        legend=dict(
            yanchor='top',
            xanchor='right'
        ),
        margin=dict(l=100, r=20, t=100, b=20),
    )

    return fig

@callback(
    Output('size_line_plot', 'figure'),
    Input('sorting_dropdown', 'value'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'))
def update_unit_price_slope_plot(sort_val, category_val, brand_val):
    df_filtered = df.copy()
    title = f'Unit price comparison of{" "+brand_val if brand_val else ""}{" "+category_val.lower() if category_val else ""} products'
    if category_val:
        df_filtered = df_filtered[df_filtered['lvl_0_cat']==category_val]
    if brand_val:
        df_filtered = df_filtered[df_filtered['brand_name']==brand_val]
    return unit_price_slope_plot(get_unit_price_comparison_data(df_filtered, sort_val), title)


def unit_price_slope_plot(df, title="Unit price comparison of products"):
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
                    "index":True
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
                    # slope plot (mini vs standard)
                    dbc.Col([
                        dbc.Card(
                            dbc.CardBody([
                                dcc.Graph(
                                    id='size_line_plot',
                                    figure=unit_price_slope_plot(get_unit_price_comparison_data(df))
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
                                    dbc.Col([
                                        html.Div(
                                            "",
                                            id='product_details_text'
                                        )
                                    ], width=2),
                                    dbc.Col([
                                        dcc.Graph(
                                            id='unit_price_hist_plot',
                                            figure=unit_price_histogram(df[df['lvl_2_cat']=='Mascaras'], 310, 'unit_price')
                                        )
                                    ], width=5),
                                    dbc.Col([
                                        dash_table.DataTable(
                                            df[(df['amount_adj']==1.0) 
                                               & (df['lvl_2_cat']=='Perfume') 
                                               & (df['unit_price']<310)].sort_values(by='unit_price', ascending=True)[['brand_name','product_name','unit_price']].to_dict("records"),
                                            [{"name": i, "id": i} for i in df[['brand_name','product_name','unit_price']].columns],
                                            page_size=5,
                                            style_cell={'textAlign': 'left',
                                                        'padding': '1px',
                                                        'fontSize':12},
                                            style_header={
                                                'backgroundColor': 'white',
                                                'fontWeight': 'bold'
                                            },
                                            style_data={
                                                'whiteSpace': 'normal',
                                                'height': 'auto',
                                            },
                                            # style_as_list_view=True,
                                            style_table={"overflowX": "auto"})
                                    ], width=5),
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
