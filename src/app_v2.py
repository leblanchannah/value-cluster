
dropdown_style = {
        'font-family': 'Poppins',
        'text':'#606060',
        'border-color':'#e2e2e2',
        'font-size':'12px',
    }

theme = {
    "accent":"#d14f96",
    "accent_negative":"#ff9f9f",
    "accent_positive":"#4ab2ff",
    "background_content":"#F2F2F2",
    "background_page":"#F9F9F9",
    "border":"#e2e2e2",
}

from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table, State
import plotly.subplots as sp
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
from PIL import ImageColor
import plotly.colors
import plotly.express as px
import plotly.graph_objects as go



df = pd.read_csv('../data/agg_prod_data.csv')

df['link'] = "["+df['product_name']+"]("+df["url"]+")"

df_compare = df[df['swatch_group']=='mini size'].merge(
    df[df['swatch_group']=='standard size'],
    on=['product_id','product_name','brand_name'],
    suffixes=('_mini','_standard'))

df_compare = df_compare[df_compare['amount_adj_mini']<df_compare['amount_adj_standard']]
# if ratio < 1, mini is better value per oz, if ratio > 1, standard is better value
df_compare['mini_to_standard_ratio'] = df_compare['unit_price_mini'] / df_compare['unit_price_standard']
df_compare = df_compare.reset_index().rename(columns={'index':'prod_rank'})


df = df.merge(
    df_compare[['product_id','product_name','brand_name','mini_to_standard_ratio']],
    on=['product_id','product_name','brand_name'],
    how='left')


df.loc[df['swatch_group'].isin(['value size','refill size']), 'mini_to_standard_ratio'] = np.nan

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='Sephora Product Analysis'
)

PLOT_TEMPLATE_THEME = 'plotly_white'
COLOUR_SCALE='Plotly3'

product_data_table = dash_table.DataTable(
    id='cheaper_product_table',
    data=df.sort_values(by='unit_price', ascending=True)[['brand_name','link','unit_price','rating']].to_dict("records"),
    columns=[
        {"name": 'Brand', "id": 'brand_name'},
        {"name": 'Product', "id": 'link', 'presentation':'markdown'},
        {"name": 'Unit Price ($/oz.)', "id": 'unit_price', 'type':'numeric', 'format':dash_table.Format.Format(precision=2, scheme=dash_table.Format.Scheme.fixed)},
        {"name": 'Rating', 'id':'rating', 'type':'numeric', 'format':dash_table.Format.Format(precision=1, scheme=dash_table.Format.Scheme.fixed)}
    ],
    sort_action="native",
    page_size=8,
    style_cell={
        'font-family':'Poppins',
        'textAlign': 'left',
        'fontSize':14,
        'overflow': 'hidden',
        'textOverflow': 'ellipsis',
        'backgroundColor':'white',

    },
    style_header={
        'fontWeight': 'bold',
        'border':'1px solid #d14f96',
        'backgroundColor':'white'
    },
    style_data={
        'border':'1px solid #d14f96',
        'whiteSpace': 'normal',
        'height': 'auto',
        'lineHeight': '15px'
    },
    style_table={
        "overflowX": "auto"
    }
)


info_button = dbc.Button("More Info", id="open-info-modal", n_clicks=0)

info_modal = html.Div([
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Header")),
            dbc.ModalBody("Hello World"),
            dbc.ModalFooter(
                dbc.Button("Close", id='close-info-modal', className='ms-auto', n_clicks=0)
            )
        ],
        id="info-modal",
        is_open=False,
    ),
])


# FORM components
product_category_l0_dropdown = dcc.Dropdown(
    id='product_category_l0_dropdown',
    options = [x for x in df.lvl_0_cat.unique() if x!=' ' and x!='Mini Size' and x!='Men'],
    value='Fragrance',
    style=dropdown_style
)

brand_dropdown = dcc.Dropdown(
    id='brand_dropdown',
    options=[x for x in df.brand_name.unique()],
    value='TOM FORD',
    style=dropdown_style
)

ratio_sorting_dropdown = dcc.Dropdown(
    id='ratio_sorting_dropdown',
    options=[],
    style=dropdown_style
)

product_options = [{'label':x.product_name+' '+x.brand_name+' '+x.swatch_group,'value':x.index} for x in df[['product_name','brand_name','index','swatch_group']].itertuples()]
product_info_dropdown = dcc.Dropdown(
    id='product_info_dropdown',
    options=product_options,
    placeholder='Dior Forever Loose Cushion Powder',
    value=4168,
    style=dropdown_style
)

max_price_filter = dcc.Input(
    id='max_price_filter',
    type='number',
    min=0,
    max=2000,
    step=5
)

def get_color(colorscale_name, loc):
    from _plotly_utils.basevalidators import ColorscaleValidator
    # first parameter: Name of the property being validated
    # second parameter: a string, doesn't really matter in our use case
    cv = ColorscaleValidator("colorscale", "")
    # colorscale will be a list of lists: [[loc1, "rgb1"], [loc2, "rgb2"], ...] 
    colorscale = cv.validate_coerce(colorscale_name)
    
    if hasattr(loc, "__iter__"):
        return [get_continuous_color(colorscale, x) for x in loc]
    return get_continuous_color(colorscale, loc)
        
# This function allows you to retrieve colors from a continuous color scale
# by providing the name of the color scale, and the normalized location between 0 and 1
# Reference: https://stackoverflow.com/questions/62710057/access-color-from-plotly-color-scale

def get_continuous_color(colorscale, intermed):
    """
    Plotly continuous colorscales assign colors to the range [0, 1]. This function computes the intermediate
    color for any value in that range.

    Plotly doesn't make the colorscales directly accessible in a common format.
    Some are ready to use:
    
        colorscale = plotly.colors.PLOTLY_SCALES["Greens"]

    Others are just swatches that need to be constructed into a colorscale:

        viridis_colors, scale = plotly.colors.convert_colors_to_same_type(plotly.colors.sequential.Viridis)
        colorscale = plotly.colors.make_colorscale(viridis_colors, scale=scale)

    :param colorscale: A plotly continuous colorscale defined with RGB string colors.
    :param intermed: value in the range [0, 1]
    :return: color in rgb string format
    :rtype: str
    """
    if len(colorscale) < 1:
        raise ValueError("colorscale must have at least one color")

    hex_to_rgb = lambda c: "rgb" + str(ImageColor.getcolor(c, "RGB"))

    if intermed <= 0 or len(colorscale) == 1:
        c = colorscale[0][1]
        return c if c[0] != "#" else hex_to_rgb(c)
    if intermed >= 1:
        c = colorscale[-1][1]
        return c if c[0] != "#" else hex_to_rgb(c)

    for cutoff, color in colorscale:
        if intermed > cutoff:
            low_cutoff, low_color = cutoff, color
        else:
            high_cutoff, high_color = cutoff, color
            break

    if (low_color[0] == "#") or (high_color[0] == "#"):
        # some color scale names (such as cividis) returns:
        # [[loc1, "hex1"], [loc2, "hex2"], ...]
        low_color = hex_to_rgb(low_color)
        high_color = hex_to_rgb(high_color)

    return plotly.colors.find_intermediate_color(
        lowcolor=low_color,
        highcolor=high_color,
        intermed=((intermed - low_cutoff) / (high_cutoff - low_cutoff)),
        colortype="rgb",
    )




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
            color_discrete_sequence=["#d14f96","#FFBEE5",],
            height=310,
            title=title,
            labels={'unit_price': "Unit Price ($/oz.)", "value":""}
        )
    
    fig.update_layout(
        yaxis_title="Product Count",
        xaxis=dict(
            autorange=True
        ),
        autosize=True,
        legend=dict(
            yanchor='top',
            xanchor='right',

        ),
        font_family="Poppins",
        font_color="#606060",
        title_font_family="Poppins",
        title_font_color="#606060",
        legend_title_font_color="#606060",
        hoverlabel=dict(
            font_family="Poppins"
        ),
        template=PLOT_TEMPLATE_THEME,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='#F9F9F9',
        paper_bgcolor='#F9F9F9'
    )
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


def normalize_colour_value(data_point, all_values):
    """
    Normalizes data point values for use with colour bar. 
    """
    return (data_point - min(all_values)) / (max(all_values) - min(all_values))


def joint_slope_scatter(df_product_pairs, df_base, slope_plot_title, scatter_plot_title):


    fig = sp.make_subplots(rows=1, cols=2, column_widths=[0.4, 0.6],
        subplot_titles=(slope_plot_title, scatter_plot_title))

    # slope plot - compare unit prices of related products
    tooltip_hover_template = '{}<br>{}<br>Size: {} oz.<br>Price: ${}<br>Category: {}<br>Mini-to-Standard Ratio: {:.2f}<br>Product ID: {}' 
    for i, row in df_product_pairs.iterrows():

        colour_val_normed = normalize_colour_value(row['mini_to_standard_ratio'], df_product_pairs['mini_to_standard_ratio'])

        pair_line_trace = go.Scatter(
            x=['Mini', 'Standard'],
            y=[row['unit_price_mini'], row['unit_price_standard']],
            mode='markers+lines',
            marker=dict(
                color=get_color(COLOUR_SCALE, colour_val_normed),
                colorscale=COLOUR_SCALE,
                showscale=False,
                cmin=min(df_product_pairs['mini_to_standard_ratio']),
                cmax=max(df_product_pairs['mini_to_standard_ratio']),
            ),  
            line=dict(
                width=5
            ),
            showlegend = False,
            hovertemplate = 'Unit Price: %{y:.2f}$/oz. <br>%{text}',  
            # each line is made of two markers, text = [marker_mini, marker_standard]
            text=[tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a_mini'],
                                                row['price_mini'], row['lvl_2_cat_mini'], row['mini_to_standard_ratio'],
                                                row['index_mini']),
                  tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a_standard'], 
                                                row['price_standard'], row['lvl_2_cat_standard'], row['mini_to_standard_ratio'],
                                                row['index_standard'])],
        )

        fig.add_trace(pair_line_trace, row=1, col=1)

    fig.add_vline(x=0, opacity=0.1, fillcolor="grey", line_width=1, layer='below', row=1, col=1)
    fig.add_vline(x=1, opacity=0.1, fillcolor="grey", line_width=1, layer='below', row=1, col=1)

    fig.update_layout(
        xaxis=dict(
            title='Product Size',
            type='category',
            tickmode='array',
            # really difficult to get categorical axis spacing right
            range=[-0.2, 1.1],
            linecolor='white', #rgb(204, 204, 204
        ),
        yaxis=dict(
            title='Unit Price ($/oz.)',
            showgrid=False,
            zeroline=True,
            showline=False,
            showticklabels=True,
        ),
        showlegend=False,
        
    )

    # right side - scatter plot
    marker_shapes = {'mini size':'circle', 'standard size':'square', 'refill size':'diamond', 'value size':'cross'}
    
    # grey markers, no mini-to-standard ratio
    df_no_ratio = df_base[df_base['mini_to_standard_ratio'].isna()]
    tooltip_hover_template = '{}<br>{}<br>Size: {} oz.<br>Price: ${}<br>Unit Price: {:.2f}$/oz.<br>Category: {}<br>Size Category: {}<br>Mini-to-Standard Ratio: {:.2f}<br>Product ID: {}' 

    background_scatter = go.Scatter(
        x=df_no_ratio['amount_a'],
        y=df_no_ratio['price'],
        mode="markers",
        marker=dict(
            size=10,
            color=['grey' for x in range(df_no_ratio.shape[0])],
            symbol=[marker_shapes[row['swatch_group']] for i, row in df_no_ratio.iterrows()],
        ),
        opacity=0.6,
        hovertemplate='%{text}',
        text=[tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a'], row['price'],
                                            row['unit_price'], row['lvl_2_cat'], row['swatch_group'],
                                            row['mini_to_standard_ratio'], row['index']) for i, row in df_no_ratio.iterrows()]
    )

    fig.add_trace(background_scatter, row=1, col=2)

    df_w_ratio = df_base[df_base['mini_to_standard_ratio'].notnull()]
    scatter_highlight = go.Scatter(
        x=df_w_ratio['amount_a'],
        y=df_w_ratio['price'],
        mode="markers",
        marker=dict(
            size=10,
            color=df_w_ratio['mini_to_standard_ratio'],
            colorbar=dict(
                title="Mini-to-Standard <br>Unit Price Ratio",
                thickness=25,
                bordercolor='white',
                outlinecolor='white',
                x=-0.2,
                xref="container",
            ),
            colorscale=COLOUR_SCALE,
            cmin=min(df_base['mini_to_standard_ratio']),
            cmax=max(df_base['mini_to_standard_ratio']),
            symbol=[marker_shapes[x['swatch_group']] for i, x in df_w_ratio.iterrows()]
        ),
        hovertemplate="%{text}",
        text=[tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a'],
                                            row['price'], row['unit_price'], row['lvl_2_cat'],
                                            row['swatch_group'],row['mini_to_standard_ratio'], row['index']) for i, row in df_w_ratio.iterrows()],
    )

    fig.add_trace(scatter_highlight, row=1, col=2)
    
    fig.update_xaxes(title_text="Size (oz.)", row=1, col=2)
    fig.update_yaxes(title_text="Price ($)", row=1, col=2)
    fig.update_layout(
        hovermode="closest",
        hoverlabel=dict(
            font_family="Poppins"
        ),
        height=380,
        template=PLOT_TEMPLATE_THEME,
        margin=dict(l=20, r=20, t=40, b=20),
        font_family="Poppins",
        font_color="#606060",
        title_font_family="Poppins",
        title_font_color="#606060",
        legend_title_font_color="#606060",
        plot_bgcolor='#F9F9F9',
        paper_bgcolor='#F9F9F9'

    )

    return fig




app.layout = dbc.Container([
    # title and filters
    dbc.Row([
        dbc.Col([
            dbc.Card(children=[
                dbc.Row([
                    dbc.Col([html.H1("Product Value Canvas")], width=4),
                    dbc.Col(
                        id='product_category_filter',
                        children=[
                            html.Label("Product Type"),
                            product_category_l0_dropdown
                        ],
                    ),
                    dbc.Col(
                        id='brand_filter',
                        children=[
                            html.Label("Brand"),
                            brand_dropdown
                        ],
                    ),

                    dbc.Col(
                        id='ratio_sorting',
                        children=[
                            html.Label("Sort Product Pairs"),
                            ratio_sorting_dropdown
                        ],
                    ),
                    dbc.Col(
                        id='price_filter',
                        children=[
                            html.Label("Maximum Price"),
                            html.Br(),
                            max_price_filter
                        ],
                    ),
                    dbc.Col(
                        id='info_navigation',
                        children=[
                            info_button,
                            info_modal
                        ]
                    ),
                ], justify="center", align="center")
            ], body=True)
        ], width=12)
    ]),
    # product comparison plots
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dcc.Graph(
                    id='slope_scatter_joint',
                )
            ], body=True)
        ])
    ]),
    # selected product info
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.Row([
                    dbc.Col([
                        dbc.Row([
                            html.H3(["Selected Product"]),
                            product_info_dropdown,
                            html.Br(),
                            html.Br()
                        ]),
                        dbc.Row([
                            dcc.Graph( 
                                id='unit_price_hist_plot',
                                config={
                                    'responsive':True,
                                    'displayModeBar': False
                                },
                             
                            )
                        ])
                    ], width=4),
                    dbc.Col([
                        html.Div(id='selected_product_info',
                                style={'margin-top':'35px'})
                        
                    ], width=2),
                    dbc.Col([
                        html.H3(['Product Recommendations']),
                        product_data_table
                    ], width=6),

                ])
            ], body=True)
        ])
    ])
],fluid=True)


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
        html.B("Product Details"),
        html.Br(),
        html.Span(f"{data['product_name']}, {data['swatch_group']}"),
        html.Br(),
        html.B("Brand: "),
        html.Span(f"{data['brand_name']}"),
        html.Br(),
        html.B("Price: "),
        html.Span(f"${data['price']}"),
        html.Br(),
        html.B("Size: "),
        html.Span(f"{data['amount_adj']} {data['unit_a']}"),
        html.Br(),
        html.Span(f"🚨 Found {num_cheaper_products} products at Sephora in {data['lvl_2_cat'].lower()} category with unit price < ${data['unit_price']:.2f} /{data['unit_a']}.")
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



    
############# CALLBACKS ############# 


@app.callback(
    Output("info-modal", "is_open"),
    [Input("open-info-modal", "n_clicks"), Input("close-info-modal", "n_clicks")],
    [State("info-modal", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


@app.callback(
        Output('product_info_dropdown','value'),
        Input('slope_scatter_joint','clickData'),
        prevent_initial_call=True
)
def select_product_chain(scatter_click_data):
    click_data = ctx.triggered[0]
    product_value = int(click_data['value']['points'][0]['text'].split("Product ID: ")[-1])
    return product_value


@app.callback(
        Output('unit_price_hist_plot','figure'),
        Input('product_info_dropdown','value')
)
def update_histogram_figure(product_value):
    data = get_single_product_data(df, product_value)
    category = data['lvl_2_cat']
    title = f'{category} Unit Price Distribution'    
    fig = unit_price_histogram(
        df[df['lvl_2_cat']==category],
        data['unit_price'],
        'unit_price',
        title=title
    )
    return fig


@app.callback(
        Output('cheaper_product_table','data'),
        Input('product_info_dropdown','value')
)
def update_table_data(product_value):
    data = get_single_product_data(df, product_value)
    cheaper_product = (df['unit_price']<data['unit_price'])
    same_category = (df['lvl_2_cat']==data['lvl_2_cat'])
    df_filtered_table = df[cheaper_product & same_category]
    table_cols = ['brand_name','link','unit_price','rating']
    table = df_filtered_table.sort_values(by='unit_price', ascending=True)[table_cols].to_dict("records")
    return table


@app.callback(
        Output('selected_product_info', 'children'),
        Input('product_info_dropdown','value'),
)
def update_product_details(product_value):
    data = get_single_product_data(df, product_value)
    product_info_text = single_product_info_box(df, data)
    return product_info_text



@app.callback(
        Output('brand_dropdown', 'options'),
        Input('product_category_l0_dropdown', 'value')
)
def set_brand_options(product_category):
    # dynamic dropdown, only allows user to select brands with products in selected category
    candidate_brands = df[df['lvl_0_cat']==product_category].groupby('brand_name', as_index=False)['index'].count()
    brand_options = candidate_brands[candidate_brands['index']>0]['brand_name'].values
    
    return brand_options



#need to add sorting option
@callback(
    Output('slope_scatter_joint','figure'),
    Input('product_category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    Input('max_price_filter', 'value'),
)
def update_joint_plot(category_val, brand_val, max_price_val):
    df_filter_pairs = df_compare.copy()
    df_filter_products = df.copy()

    if category_val:
        df_filter_pairs = df_filter_pairs[df_filter_pairs['lvl_0_cat_standard']==category_val]
        df_filter_products = df_filter_products[df_filter_products['lvl_0_cat']==category_val]

    if brand_val:
        df_filter_pairs = df_filter_pairs[df_filter_pairs['brand_name']==brand_val]
        df_filter_products = df_filter_products[df_filter_products['brand_name']==brand_val]

    if max_price_val:
        df_filter_pairs = df_filter_pairs[df_filter_pairs['price_standard']<max_price_val]
        df_filter_products = df_filter_products[df_filter_products['price']<max_price_val]

    pair_title = f'Unit Price Comparison Of{" "+brand_val.title() if brand_val else ""}{" "+category_val.title() if category_val else ""} Products '
    scatter_title = f'Explore{" "+brand_val.title() if brand_val else ""}{" "+category_val.title() if category_val else ""} Products By Size And Price'

    
    return joint_slope_scatter(df_filter_pairs, df_filter_products, pair_title, scatter_title)
        
if __name__ == '__main__':
    app.run_server(debug=True)
