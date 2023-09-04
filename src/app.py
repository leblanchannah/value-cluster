from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px


# styling elements - need to move these to separate CSS eventually. 
PLOT_TEMPLATE_THEME = 'simple_white'
MARKER_COLOURS = ["#ff001a","#6e098d","#8b5fbf","#2b1930","#d183c9","#FFBEE5","#e84bb1","#8e0827","#8d46a3","#c61083"]
font_sizes = {
    'legend_title':12,
    'legend_item':10,
    'plot_title':16,
    'axis_label':14,
    'h1_title':26,
    'sidebar_text':14
}

SIDEBAR_STYLE = {
    "top": 0,
    "left": 0,
    "bottom": 0,
    "background-color": "#F8E1F2"
}

####### DATA 
# product data, aggregated to single row per product - need to move this to separate file or use plotly data store  
df = pd.read_csv('/home/leblanchannah/value-cluster/data/agg_prod_data.csv')
# volume errors
df = df[~df['index'].isin([4879, 3506, 6904, 6286, 4186, 6286, 5649, 2000, 5641, 6282, 6268])]


# Initialize the Dash app
app = Dash(__name__)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='Sephora Product Analysis',
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# Sidebar elements 

# Drop down used to sort slope plot
sorting_dropdown = dcc.Dropdown(
                        options=[
                            {'label':'Increasing Unit Price Ratio','value':'ratio_mini_lt_full'},
                            {'label':'Decreasing Unit Price Ratie','value':'ratio_full_lt_mini'},
                            {'label':'Best Value Mini Products','value':'unit_price_mini'},
                            {'label':'Best Value Standard Products','value':'unit_price_full'},
                        ],
                        value='ratio_full_lt_mini',
                        id='sorting_dropdown',
                        optionHeight=70,
                    )


# Drop down used to filter both slope and scatter plots by brand
brand_filter_global = dcc.Dropdown(
                            options = [x for x in df.brand_name.unique()],
                            id='brand_dropdown'
                    )


# Drop down used to filter both slope and scatter plots by product category
product_category_l0_global = dcc.Dropdown(
                                    options = [x for x in df.lvl_0_cat.unique() if x!=' ' and x!='Mini Size' and x!='Men'],
                                    value='Makeup',
                                    id='category_l0_dropdown',
                            )


min_price_filter = dcc.Dropdown(
                    options = [{'label':f'$ {x:.2f}', 'value':x} for x in range(0, 200, 10)],
                    placeholder='Minimum',
                    searchable=False,
                    clearable=True,
                    id='min_price_dropdown',
                    style={'width':'100%'}
                )


def max_price_filter(df, price_col):
    '''
        dynamic max price dropdown filter uses maximum product price in the dataset 
    '''
    max_price = int(df[price_col].max())
    return dcc.Dropdown(
                    options = [{'label': f'$ {x:.2f}', 'value': x} for x in range(1500, 0, -100)],
                    placeholder='Maximum',
                    searchable=False,
                    clearable=True,
                    id='max_price_dropdown',
                    style={'width': '100%'})


github_link = html.A("GitHub Repo", href="https://github.com/leblanchannah/value-cluster", style={'color':'#D13CAA'})


credit_link = html.P([
    'This dashboard is inspired by the "Sephora Minis Math" TikTok by ',
    html.A("@michaelamakeup92", href="https://www.tiktok.com/@michaelamakeup92/video/7237211338618047787", style={'color':'#D13CAA'}),
])


data_update =  html.P(["Data last updated on 22/08/2023."])


# select single product - used in selected product section 
product_options = [{'label':x.product_name+' '+x.brand_name+' '+x.swatch_group,'value':x.index} for x in df[['product_name','brand_name','index','swatch_group']].itertuples()]
product_dropdown = dcc.Dropdown(
                        options=product_options,
                        placeholder='Dior Forever Loose Cushion Powder',
                        value=4168,
                        id='product_dropdown',
                        optionHeight=70,
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
    # note: sephora product categories came from breadcrumbs on product pages, l2 is most specific level 
    unit_price = (df['unit_price']<data['unit_price']) 
    l2_type = (df['lvl_2_cat']==data['lvl_2_cat']) 
    num_cheaper_products = df[unit_price & l2_type].shape[0]
    return [
        html.H5(['Details'], style={'font-size':font_sizes['plot_title']}),
        f"Product: {data['product_name']}, {data['swatch_group']}",
        html.Br(),
        f"Brand: {data['brand_name']}",
        html.Br(),
        f"Price: ${data['price']}",
        html.Br(),
        f"Size: {data['amount_adj']} {data['unit_a']}", 
        html.Br(),
        f"🚨 Found {num_cheaper_products} products at Sephora in {data['lvl_2_cat'].lower()} category with unit price < ${data['unit_price']:.2f} /{data['unit_a']}."
    ]


def get_single_product_data(df, row_id, index_col='index'):
    '''
    Args:
        df - data
        row_id - product id  
        index_col - col to search for id in 
    Returns:
        single row from db corresponding to selected product as dictionary
    '''
    return df[df[index_col]==row_id].to_dict('records')[0]


def basic_df_sort(df, col, asc=True, limit=10):
    '''
    '''
    return df.sort_values(by=col, ascending=asc).head(limit)


def sort_product_comparison_data(df, dropdown_value, limit=10):
    '''
    Sorting dropdown focused on sorting data using unit price values and rations 
    Args:
        df - data
        dropdown_value - string value from dropdown options
    Returns:
        dataframe sorted based on selection in sorting dropdown in sidebar
        # of entries returned based on limit - 10 is suggested bc lineplot can look busy 
    '''
    if dropdown_value=='ratio_mini_lt_full':
        # products where the mini unit price is cheaper than full
        return basic_df_sort(df, 'mini_to_standard_ratio', asc=True, limit=limit)
    elif dropdown_value=='ratio_full_lt_mini':
        # products where the full unit price is cheaper than mini
        return basic_df_sort(df, 'mini_to_standard_ratio', asc=False, limit=limit)
    elif dropdown_value=='unit_price_mini':
        # cheapest minis by product price
        return basic_df_sort(df, 'unit_price_mini', asc=True, limit=limit)
    elif dropdown_value=='unit_price_full':
        # cheapest full sized products by unit price
        return basic_df_sort(df, 'unit_price_standard', asc=True, limit=limit)
    else:
        return df
    

def get_unit_price_comparison_data(df, sorting_value='ratio_mini_lt_full'):
    '''
    Preprocessing required to compare mini and standard size products with one another 
    Args:
    Returns:
    '''
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
    df_compare['pretty_ratio'] = df_compare['mini_to_standard_ratio'].round(2).astype(str)
    df_compare['display_name'] = df_compare['brand_name']+",<br>"+df_compare['lvl_2_cat']+" ("+df_compare['pretty_ratio']+")"
    return df_compare


##### FIGURES
def product_unit_price_v_size_scatter(df, title='Explore Products By Size And Price'):
    '''
    Exploratory scatter plot that shows product size V product price, despite misleading function name....
    Product swatchgroup category is used in legend - standard, mini, value, refill
    This plot is linked to callbacks from category, brand and price filters 
    Args:
        df - data
        title - title of plot, will be expanded depending on selected filters using callbacks
    Returns:
        plotly express figure
    '''
    fig = px.scatter(
                    df,
                    x='amount_adj',
                    y='price',
                    color='swatch_group',
                    title=title,
                    template=PLOT_TEMPLATE_THEME,
                    height=420,
                    color_discrete_sequence=["#2b1930","#8b5fbf","#e84BB1","#FF001A"],
                    hover_data=['brand_name', 'product_name', 'index'],
                    labels={'amount_adj': "Product Size (oz.)",  'price': "Price ($)", "swatch_group": "Product Size"}
    )

    fig.update_layout(
        autosize=True,
        legend=dict(
            yanchor='top',
            xanchor='right',
            title_font_size=font_sizes['legend_title'],
            font_size=font_sizes['legend_item'],
        ),
        margin=dict(l=50, r=20, t=50, b=50),
        title_font_size=font_sizes['plot_title']
    )

    fig.update_xaxes(title_font_size=font_sizes['axis_label'])
    fig.update_yaxes(title_font_size=font_sizes['axis_label'])

    legend_item_names = {
        'standard size':'Standard',
        'mini size': 'Mini',
        'refill size':'Refill',
        'value size':'Value'
    }
    fig.for_each_trace(lambda t: t.update(name = legend_item_names[t.name],
                                        legendgroup = legend_item_names[t.name],
                                        hovertemplate = t.hovertemplate.replace(t.name, legend_item_names[t.name])
                                        )
                    )
    fig.update_traces(marker=dict(size=8,opacity=0.9))
    return fig


def unit_price_histogram(data, position, unit_price_col, title='Unit Price Distribution'):
    '''
    Unit price histogram shows distribution of unit prices for selected product category
    and shows the area of distribution where products are better value than the selected product using different bin colours
        https://stackoverflow.com/questions/71778342/highlight-one-specific-bar-in-plotly-bar-chart-python
    This plot and its title are updated when selected product dropdown is used 
    Args:
        data - product dataframe input
        position - id of selected product in dataframe
        unit_price_col - name of unit price col in dataframe
        title - title for plot, product category will be appended to this 
    Returns:
        plotly express figure
    '''
    # adding new column to dataframe to label cheaper products 
    m_rows = data.shape[0]
    if m_rows==0:
        m_rows=1
    data['value'] = 'expensive'
    data.loc[data[unit_price_col]<position, 'value'] = 'cheaper'
    cheaper_products = data[data['value']=='cheaper'].shape[0]
    pct_cheaper = round((cheaper_products/m_rows)*100, 2)
    
    fig = px.histogram(
            data,
            x=unit_price_col,
            color='value',
            template=PLOT_TEMPLATE_THEME,
            color_discrete_sequence=["#e84bb1","#FFBEE5",],
            height=320,
            title=title,
            labels={'unit_price': "Unit Price ($/oz.)", "value":""}
        )
    
    fig.update_layout(
        margin=dict(l=50, r=50, t=50, b=0, pad=0),
        yaxis=dict(
            autorange=True,
        ),
        yaxis_title="Product Count",
        xaxis=dict(
            autorange=True
        ),
        title_font_size=font_sizes['plot_title'],
        autosize=True,
        legend=dict(
            yanchor='top',
            xanchor='right',
            title_font_size=font_sizes['legend_title'],
            font_size=font_sizes['legend_item'],
        )
    )

    fig.update_xaxes(title_font_size=font_sizes['axis_label'])
    fig.update_yaxes(title_font_size=font_sizes['axis_label'])

    # need to use update traces to change plotly legend item names 
    fig.update_traces(
        showlegend=True
    )
    legend_labels = {
        'cheaper':f'{pct_cheaper}% - better value per<br>unit than selected',
        'expensive': f'{round(100-pct_cheaper,2)}% - more expensive per<br>unit than selected',
    }
    fig.for_each_trace(lambda t: t.update(name = legend_labels[t.name],
                                        legendgroup = legend_labels[t.name],
                                        hovertemplate = t.hovertemplate.replace(t.name, legend_labels[t.name])
                                        )
                    )
    return fig


def unit_price_slope_plot(df, title="Unit Price Comparison Of Products", legend_title='Product, Unit Price Ratio'):
    '''
    Compares unit price of standard-mini product pairs in dataset
    This plot data and title are updated by callbacks from sorting, category, brand and price dropdowns 
    Args:
        df - data
        title - title of plot 
        legend_title - 
    Returns:
        plotly express figure
    '''
    fig = px.line(
                df,
                y="value",
                x="variable",
                color="prod_rank",
                height=420,
                title=title,
                template=PLOT_TEMPLATE_THEME,
                color_discrete_sequence=MARKER_COLOURS,
                hover_data={
                    "brand_name":True,
                    "product_name":True,
                    "amount_adj_mini":':.2f',
                    "amount_adj_standard":':.2f',
                    "mini_to_standard_ratio":':.2f',
                    "prod_rank":False,
                    "index":True
                },
                markers=True
    )

    fig.update_layout(
        margin=dict(l=50, r=20, t=50, b=50),
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
            # really difficult to get categorical axis spacing right
            range=[-0.2, 2 - 0.7],
        ),
        legend=dict(
            title=legend_title,
            title_font_size=font_sizes['legend_title'],
            font_size=font_sizes['legend_item'],
            yanchor='top'
        ),
        title_font_size=font_sizes['plot_title'],
        hoverlabel = dict(
        )
    )

    fig.update_xaxes(title_font_size=font_sizes['axis_label'])
    fig.update_yaxes(title_font_size=font_sizes['axis_label'])

    # map line index to brand+category label
    legend_name_map = {row['prod_rank']:row['display_name'] for index, row in df.iterrows()}
    fig.for_each_trace(lambda t: t.update(name = legend_name_map[int(t.name)]))
    fig.update_traces(line=dict(width=5), marker=dict(size=10))
    return fig 

###### App 
app.layout = dbc.Container([
        dbc.Row([
            # side panel col, with title, description etc 
            dbc.Col([
                dbc.Row(
                    id='app_title',
                    children=[
                        dbc.Col([
                            html.H1("Sephora Value Canvas",
                                style={
                                    'color':'#B1298D',
                                    'font-size':font_sizes['h1_title'],
                                    'text-align':'center',
                                    'paddingTop':'1rem',
                                }),
                        ], width=12)
                    ]
                ),
                dbc.Row(
                    id='abstract',
                    children=[
                        dbc.Col([
                            html.P([
                                '''
                                The unit prices of products at Sephora are not readily available without web scraping. 
                                This tool facilitates a comparison between products available in both mini and standard sizes by analyzing their unit price ratios.
                                '''],
                                style={'font-size':font_sizes['sidebar_text']}
                                ),
                                dcc.Markdown(
                                    '$$\\small{ValueR=}\\normalsize{\\frac{MiniUnitPrice}{StandardUnitPrice}}$$',
                                    mathjax=True,
                                    style={'width':'%80'}
                                ),
                                html.P([
                                    '''
                                    Interpretation: A unit price ratio value of 4 means the mini size is 4x more expensive per ounce than its standard size counterpart.

                                    '''],
                                    style={'font-size':font_sizes['sidebar_text']}
                                ),
                        ], width=12)
                    ]
                ),
                dbc.Row(
                    id='sorting_section',
                    children=[
                        dbc.Col([
                            html.Label("Sort:", style={'color':'#643A71'}),
                        ], width=4),
                        dbc.Col([
                            sorting_dropdown
                        ], width=8)
                    ],
                    align='center',
                ),
                dbc.Row(
                    id='filter_title',
                    children=[
                        dbc.Col([     
                        ], width=12)
                    ]
                ),
                dbc.Row(
                    id="product_category_filter",
                    children=[
                        dbc.Col([
                            html.Label("Category:", style={'color':'#643A71'}),
                        ], width=4),
                        dbc.Col([
                            product_category_l0_global
                        ], width=8)
                    ],
                align='center',
                style={'paddingTop':'1rem'},
                ),
                dbc.Row(
                    id='brand_filter',
                    children=[
                        dbc.Col([
                            html.Label("Brand:", style={'color':'#643A71'}),
                        ], width=4),
                        dbc.Col([
                            brand_filter_global
                        ], width=8),
                    ], 
                    align='center',
                    style={'paddingTop':'1rem'},
                ),
                dbc.Row(
                    id='price_filters',
                    children=[
                        dbc.Col([
                            html.Label("Price:", style={'color':'#643A71'}),
                        ], width=4),
                        dbc.Col([
                            min_price_filter
                        ], width=4, style={'paddingRight':'0.1rem'}),
                        dbc.Col([
                            max_price_filter(df, 'price')
                        ], width=4, style={'paddingLeft':'0.1rem'})
                    ],
                    align='center',
                    style={'paddingTop':'1rem'},
                ),
                dbc.Row(
                    id='footnotes',
                    children=[
                        dbc.Col([
                            html.Br(),
                            credit_link,
                            github_link,
                            data_update
                        ], style={'font-size':font_sizes['sidebar_text']})
                    ]
                )
            ], width=2, style=SIDEBAR_STYLE),
            # data viz col
            dbc.Col([
                dbc.Row(
                    id='data_vis_all_products',
                    children=[
                        # slope plot (mini vs standard)
                        dbc.Col([
                            dcc.Graph(
                                id='size_line_plot',
                                figure=unit_price_slope_plot(get_unit_price_comparison_data(df)),
                                config={
                                    'displayModeBar': False
                                },
                                style = {
                                    'height': '100%',
                                    'width': '100%',
                                    # "border":"1px black solid"
                                }
                            )
                        ], width=6),
                        dbc.Col([
                            dcc.Graph(
                                id='scatter_products',
                                figure=product_unit_price_v_size_scatter(df),
                                style = {
                                    'height': '100%',
                                    'width': '100%'
                                }
                            )
                        ], width=6),
                    ],
                    style={
                        'paddingTop':'1%',
                        'paddingLeft':'1%',
                        'paddingRight':'1%'
                    }
                ), 
                dbc.Row([
                    dbc.Col([
                        dbc.Row(
                            id='single_product_selection',
                            children=[
                                dbc.Col([
                                    html.Label(['Selected Product'],style={'color':'#B1298D', 'font-size':'20px'}),
                                    
                                ], width=2),
                                dbc.Col([
                                    product_dropdown,
                                ], width=3),
                                dbc.Col([], width=7)
                            ],
                            style={
                                'align':'center'

                            }
                        ), 
                        dbc.Row([
                            dbc.Col([
                                html.Div(
                                    "",
                                    id='product_details_text',
                                    style={'font-size':font_sizes['sidebar_text']},
                                )
                            ], width=2),
                            dbc.Col([
                                dcc.Graph(
                                    id='unit_price_hist_plot',
                                    figure=unit_price_histogram(df[df['lvl_2_cat']=='Mascaras'], 310, 'unit_price'),
                                    config={
                                        'responsive':True,
                                        'displayModeBar': False
                                    }, 
                                    style={'height': '100%'})
                            ], width=4),
                            dbc.Col([
                                html.H5(
                                    children=["Product Recommendations"],
                                    style={
                                        'font-size':font_sizes['plot_title']
                                    }),
                                dash_table.DataTable(
                                    id='cheaper_product_table',
                                    data=df.sort_values(by='unit_price', ascending=True)[['brand_name','product_name','unit_price','rating']].to_dict("records"),
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
                                    })
                            ], width=6),
                        ])
                    ],width=12)
                ], style={
                    'margin-top':'1%',
                    'margin-left':'1%',
                    'margin-right':'1%',
                    'background-color':'white'
                    })
            ], width=10, style={'background-color':'white'}),
        ]),
], 
fluid=True,
style={'height':'100vh'}
)

############# CALLBACKS ############# 

@callback(
    Output('scatter_products', 'figure'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    Input('min_price_dropdown', 'value'),
    Input('max_price_dropdown', 'value'))
def update_product_scatter(category_val, brand_val, min_price_dropdown, max_price_dropdown):
    '''
    Args:
    Returns:
    '''
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


@callback(
    Output('size_line_plot', 'figure'),
    Input('sorting_dropdown', 'value'),
    Input('category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    Input('min_price_dropdown', 'value'),
    Input('max_price_dropdown', 'value'))
def update_unit_price_slope_plot(sort_val, category_val, brand_val, min_price_dropdown, max_price_dropdown):
    '''
    Args:
    Returns:
    '''
    df_filtered = df.copy()
    title = f'Top 10{" "+brand_val.title() if brand_val else ""}{" "+category_val.title() if category_val else ""} Products '
    sorting = {
        'ratio_mini_lt_full':'Sorted By<br>Increasing Unit Price Ratio',
        'ratio_full_lt_mini':'Sorted By<br>Decreasing Unit Price Ratio ',
        'unit_price_mini':'Sorted By<br>Best Value Mini Unit Price',
        'unit_price_full':'Sorted By<br>Best Value Standard Unit Price'
    }
    if category_val:
        df_filtered = df_filtered[df_filtered['lvl_0_cat']==category_val]
    if brand_val:
        df_filtered = df_filtered[df_filtered['brand_name']==brand_val]
    if min_price_dropdown:
        df_filtered = df_filtered[df_filtered['price']>=min_price_dropdown]
    if max_price_dropdown:
        df_filtered = df_filtered[df_filtered['price']<max_price_dropdown]


    title = title + sorting[sort_val]
    return unit_price_slope_plot(get_unit_price_comparison_data(df_filtered, sort_val), title, legend_title="Product, Unit Price Ratio")


@callback(
    Output('product_details_text', 'children'),
    Output('unit_price_hist_plot', 'figure'),
    Output('cheaper_product_table','data'),
    Input('scatter_products', 'clickData'),
    Input('size_line_plot', 'clickData'),
    Input('product_dropdown','value'))
def update_product_details(scatter_click_value, slope_click_value, product_value):
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
        if 'prop_id' in click_data.keys() and click_data['prop_id']=='product_dropdown.value':
            product_row_id = click_data['value']
        else:
        # either scatterplot or slope plot has been clicked
        # index must always be last item in custom_data, regardless of what plot it came from 
            product_row_id = click_data['value']['points'][0]['customdata'][-1]
    else:
        product_row_id = 4168
    data = get_single_product_data(df, product_row_id)

    df_filtered_hist = df[df['lvl_2_cat']==data['lvl_2_cat']]
    title = f'Unit Price of {data["lvl_2_cat"].title()} Category'
    fig = unit_price_histogram(df_filtered_hist, data['unit_price'], 'unit_price', title=title)
    
    text = single_product_info_box(df, data)
    table_cols = ['brand_name','product_name','unit_price','rating']
    df_filtered_table = df_filtered_hist[df_filtered_hist['unit_price']<data['unit_price']]
    table = df_filtered_table.sort_values(by='unit_price', ascending=True)[table_cols].to_dict("records")
    return  text, fig, table


# Run the app
if __name__ == '__main__':
    app.run_server(debug=False)
