from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

# legend title size
# legend item size 
# plot title size
# plot axis label size 

app = Dash(__name__)


PLOT_TEMPLATE_THEME = 'simple_white'
MARKER_COLOURS = px.colors.qualitative.Bold
print(MARKER_COLOURS)

# product data, aggregated to single row per product  
df = pd.read_csv('../data/agg_prod_data.csv')

# Initialize the Dash app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title='Sephora Product Analysis',
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# 
sidebar_text = html.P([
        html.A("GitHub Repo", href="https://github.com/leblanchannah/value-cluster"),
        html.Br(),
        """
            This dashboard is inspired by the "Sephora Minis Math" TikTok by
        """,
        html.A("@michaelamakeup02's", href="https://www.tiktok.com/@michaelamakeup92/video/7237211338618047787"),
        html.Br()
], style={'font-size':14})

# Drop down used to sort slope plot
sorting_dropdown = dcc.Dropdown(
                        options=[
                            {'label':'Mini to full unit price ratio','value':'ratio_mini_lt_full'},
                            {'label':'Full to mini unit price ratio','value':'ratio_full_lt_mini'},
                            {'label':'Best value mini sizes','value':'unit_price_mini'},
                            {'label':'Best value full sizes','value':'unit_price_full'},
                        ],
                        value='unit_price_mini',
                        id='sorting_dropdown',
                        style=dict(width='100%')
                    )

# Drop down used to filter both slope and scatter plots by brand
brand_filter_global = dcc.Dropdown(
                        options = [x for x in df.brand_name.unique()],
                        id='brand_dropdown',
                        style=dict(width='100%')
                    )

# Drop down used to filter both slope and scatter plots by product category
product_category_l0_global = dcc.Dropdown(
                                options = [x for x in df.lvl_0_cat.unique() if x!=' ' and x!='Mini Size' and x!='Men'],
                                value='Skincare',
                                id='category_l0_dropdown',
                                style=dict(width='100%')
                            )


def price_min_max_filter(df, price_col):
    '''
    '''
    max_price = int(df[price_col].max())
    return html.Div(
        children = [
            html.Div([
                dcc.Dropdown(
                    options = [{'label':f'$ {x:.2f}', 'value':x} for x in range(0, 200, 10)],
                    placeholder='Minimum',
                    searchable=False,
                    clearable=True,
                    id='min_price_dropdown'
                )],
                style={"width": "100%"},
            ),
            # need more space here
            html.Div([
                dcc.Dropdown(
                    options = [{'label': f'$ {x:.2f}', 'value': x} for x in range(1500, 0, -100)],
                    placeholder='Maximum',
                    searchable=False,
                    clearable=True,
                    id='max_price_dropdown'
                )],
                
                style={"width": "100%"}
            )
        ],
        id='price_filters',
        # style=dict(display='flex')
    )


def single_product_info_box(df, data):
    ''' 
        Product details box outlines features for a product selected on the slope plot or scatter plot.
        Example text returned 
            Product: prep + prime highlighter, standard size
            Brand: mac cosmetics
            Price: $37.0
            Size: 0.12 oz

            There are 79 highlighter products at Sephora with unit price less than 308.33 $/oz
        Args:
            df - product dataset as pd dataframe
            data - dictionary of data describing product selected
        Returns:
    '''
    # identify number of products with lower unit price within the same product category
    # note: sephora product categories came from breadcrumbs on product pages, l2 is most specific level 
    unit_price = (df['unit_price']<data['unit_price']) 
    l2_type = (df['lvl_2_cat']==data['lvl_2_cat']) 
    num_cheaper_products = df[unit_price & l2_type].shape[0]
    return [
        html.H4('Selected Product Details'),
        f"Product: {data['product_name']}, {data['swatch_group']}",
        html.Br(),
        f"Brand: {data['brand_name']}",
        html.Br(),
        f"Price: ${data['price']}",
        html.Br(),
        f"Size: {data['amount_adj']} {data['unit_a']}", 
        html.Br(),
        f"There are {num_cheaper_products} {data['lvl_2_cat'].lower()} at Sephora with unit price less than ${data['unit_price']:.2f} /{data['unit_a']}."
    ]


@callback(
    Output('product_details_text', 'children'),
    Output('unit_price_hist_plot', 'figure'),
    Output('cheaper_product_table','data'),
    Input('scatter_products', 'clickData'),
    Input('size_line_plot', 'clickData'))
def update_product_details(scatter_click_value, slope_click_value):
    '''
        When a data point is clicked on the slope pair plot OR the product scatter plot, the product details section is updated
        to show information on the selected product. 
        Args:
            scatter_click_value - callback info
            slope_click_value - callback info
                although callback info is provided, it is easier for me to use callback context -> ctx when determining what was
                most recently clicked on the dashboard. 
        Returns:
            Tuple of updates 
            - updates div children (id=product_details_text) with text describing produce selected, along with recommendation 
            - updates histogram figure (id=unit_price_hist_plot) with unit prices of products in same l2 category as selected product
            - updates table data (id=cheaper_product_table) with better value products than the selected product

    '''
    # sequential clicks show data in both scatter value and slope value - making it difficult to tell what is most recent
    # ctx triggered gives most recent and all the same data under customdata key
    click_data = ctx.triggered[0]
    if click_data['value'] is not None:
        # either scatterplot or slope plot has been clicked
        # index must always be last item in custom_data, regardless of what plot it came from 
        product_row_id = click_data['value']['points'][0]['customdata'][-1]
    else:
        product_row_id = 2843
    data = get_single_product_data(df, product_row_id)
    
    df_filtered_hist = df[df['lvl_2_cat']==data['lvl_2_cat']]
    title = f'Unit Price Distribution, {data["lvl_2_cat"].title()}'
    fig = unit_price_histogram(df_filtered_hist, data['unit_price'], 'unit_price', title=title)
    
    text = single_product_info_box(df, data)

    df_filtered_table = df_filtered_hist[df_filtered_hist['unit_price']<data['unit_price']]
    table = df_filtered_table.sort_values(by='unit_price', ascending=True)[['brand_name','product_name','unit_price']].to_dict("records")
    return  text, fig, table


def unit_price_histogram(data, position, unit_price_col, title='Unit Price Distribution'):
    '''
    https://stackoverflow.com/questions/71778342/highlight-one-specific-bar-in-plotly-bar-chart-python
    '''
    data['value'] = ''
    data.loc[data[unit_price_col]<position, 'value'] = 'Cheaper than selected product'

    fig = px.histogram(
            data,
            x=unit_price_col,
            color='value',
            template=PLOT_TEMPLATE_THEME,
            color_discrete_sequence=['rgb(242, 183, 1)','rgb(207, 28, 144)'],
            height=250,
            title=title,
            labels={'unit_price': "Unit Price ($/oz.)", "value":"Unit Price Distribution"}
        )
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(
            autorange=True,
        ),
        yaxis_title="Product Count",
        xaxis=dict(
            autorange=True
        ),
        autosize=True,
        legend=dict(
            yanchor='top',
            xanchor='right'
        )
    )
    fig.update_traces(
        showlegend=False
    )
    return fig


def get_single_product_data(df, row_id, index_col='index'):
    # must return single row of data as dictionary
    return df[df[index_col]==row_id].to_dict('records')[0]


@callback(
    Output('scatter_products', 'figure'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    Input('min_price_dropdown', 'value'),
    Input('max_price_dropdown', 'value'))
def update_product_scatter(category_val, brand_val, min_price_dropdown, max_price_dropdown):
    triggered_id = ctx.triggered_id 
    df_filtered = df.copy()
    title = f'Explore{" "+brand_val.title() if brand_val else ""}{" "+category_val.title() if category_val else ""} Products By Size And Price'
    if category_val:
        df_filtered = df_filtered[df_filtered['lvl_0_cat']==category_val]
    if brand_val:
        df_filtered = df_filtered[df_filtered['brand_name']==brand_val]
    if min_price_dropdown:
        df_filtered = df_filtered[df_filtered['price']>=min_price_dropdown]
    if max_price_dropdown:
        df_filtered = df_filtered[df_filtered['price']<max_price_dropdown]
    return product_unit_price_v_size_scatter(df_filtered, title)


##### Plotly figures and callbacks
def product_unit_price_v_size_scatter(df, title='Explore Products By Size And Price'):
    
    fig = px.scatter(
                    df,
                    x='amount_adj',
                    y='price',
                    color='swatch_group',
                    title=title,
                    template=PLOT_TEMPLATE_THEME,
                    # order_by='swatch_group',
                    color_discrete_sequence=MARKER_COLOURS,
                    hover_data=['brand_name', 'product_name', 'index'],
                    labels={ # replaces default labels by column name
                        'amount_adj': "Product Size (oz.)",  'price': "Price ($)", "swatch_group": "Product Size"
                    }
    )
    fig.update_layout(
        autosize=True,
        legend=dict(
            yanchor='top',
            xanchor='right'
        ),
        margin=dict(l=80, r=20, t=50, b=20),
    )

    newnames = {
        'standard size':'Standard',
        'mini size': 'Mini',
        'refill size':'Refill',
        'value size':'Value'
    }
    fig.for_each_trace(lambda t: t.update(name = newnames[t.name],
                                        legendgroup = newnames[t.name],
                                        hovertemplate = t.hovertemplate.replace(t.name, newnames[t.name])
                                        )
                    )
    fig.update_traces(marker=dict(size=10,opacity=0.8))
    return fig

@callback(
    Output('size_line_plot', 'figure'),
    Input('sorting_dropdown', 'value'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    Input('min_price_dropdown', 'value'),
    Input('max_price_dropdown', 'value'))
def update_unit_price_slope_plot(sort_val, category_val, brand_val, min_price_dropdown, max_price_dropdown):
    df_filtered = df.copy()
    title = f'Unit Price Comparison Of{" "+brand_val.title() if brand_val else ""}{" "+category_val.title() if category_val else ""} Products'
    if category_val:
        df_filtered = df_filtered[df_filtered['lvl_0_cat']==category_val]
    if brand_val:
        df_filtered = df_filtered[df_filtered['brand_name']==brand_val]
    if min_price_dropdown:
        df_filtered = df_filtered[df_filtered['price']>=min_price_dropdown]
    if max_price_dropdown:
        df_filtered = df_filtered[df_filtered['price']<max_price_dropdown]
    return unit_price_slope_plot(get_unit_price_comparison_data(df_filtered, sort_val), title)


def unit_price_slope_plot(df, title="Unit Price Comparison Of Products"):
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
                color_discrete_sequence=MARKER_COLOURS,
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
        margin=dict(l=80, r=20, t=50, b=20),
        autosize=True,
        yaxis = dict(
            title='Unit Price ($/oz.)'
        ),
        xaxis = dict(
            title='Product Size',
            type='category',
            tickmode='array',
            tickvals=['unit_price_mini', 'unit_price_standard'],
            ticktext=['Mini','Standard'],
            range=[-0.3, 2 - 0.7]
        ),
        legend=dict(
            title="Top 10 Products",
            font_size=10,
            yanchor='top'
        ),
        hoverlabel = dict(
        # option to change text in hoverlabel
        )
    )
    # map line index to brand+category label
    legend_name_map = {row['prod_rank']:row['display_name'] for index, row in df.iterrows()}
    fig.for_each_trace(lambda t: t.update(name = legend_name_map[int(t.name)]))
    fig.update_traces(line=dict(width=6))
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
    df_compare['display_name'] = df_compare['brand_name']+",<br>"+df_compare['lvl_2_cat']
    return df_compare

###### App 
app.layout = dbc.Container([
        dbc.Row([
            # side panel col, with title, description etc 
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H3("Sephora Product Analysis")),
                    dbc.CardBody([
                        html.H5("Sort By:"),
                        sorting_dropdown,
                        html.Br(),
                        html.H5("Filter:"),
                        html.B("Product Category"),
                        product_category_l0_global,
                        html.B("Brand"),
                        brand_filter_global,
                        html.B("Product Price"),
                        price_min_max_filter(df, 'price'),
                        sidebar_text,
                    ])
            ])
            ], width=2),
            # data viz col
            dbc.Col([
                dbc.Row([
                    # slope plot (mini vs standard)
                    dbc.Col([
                        dbc.Card(
                            dbc.CardBody([
                                dcc.Graph(
                                    id='size_line_plot',
                                    figure=unit_price_slope_plot(get_unit_price_comparison_data(df)),
                                    config={
                                        'displayModeBar': False
                                    }
                                )
                            ])
                        )
                    ], width=6),
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
                                            id='product_details_text',
                                            style={'font-size':16}
                                        )
                                    ], width=3),
                                    dbc.Col([
                                        dcc.Graph(
                                            id='unit_price_hist_plot',
                                            figure=unit_price_histogram(df[df['lvl_2_cat']=='Mascaras'], 310, 'unit_price'),
                                            config={
                                                'displayModeBar': False
                                            }
                                        )
                                    ], width=4),
                                    dbc.Col([
                                        dash_table.DataTable(
                                            id='cheaper_product_table',
                                            data=df.sort_values(by='unit_price', ascending=True)[['brand_name','product_name','unit_price']].to_dict("records"),
                                            columns=[
                                                {"name": 'Brand', "id": 'brand_name'},
                                                {"name": 'Product', "id": 'product_name'},
                                                {"name": 'Unit Price ($/oz.)', "id": 'unit_price', 'type':'numeric', 'format':dash_table.Format.Format(precision=2, scheme=dash_table.Format.Scheme.fixed)}
                                            ],
                                            page_size=5,
                                            style_cell={
                                                'textAlign': 'left',
                                                # 'padding': '1px',
                                                'fontSize':12,
                                                'overflow': 'hidden',
                                                'textOverflow': 'ellipsis',
                                            },
                                            style_header={
                                                'backgroundColor': 'white',
                                                'fontWeight': 'bold'
                                            },
                                            style_data={
                                                'whiteSpace': 'normal',
                                                'height': 'auto',
                                                'lineHeight': '15px'
                                            },
                                            style_table={
                                                "overflowX": "auto"
                                            })
                                    ], width=5),
                                ])
                            ]))
                    ],width=12)

                ])
            ], width=10),  html.Br(),
        ]),

], 
fluid=True,
className="dbc bg-light"
)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
