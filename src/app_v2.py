from dash import Dash, html, dcc, Input, Output, callback, ctx, dash_table
import plotly.subplots as sp
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
from PIL import ImageColor
import plotly.colors
import plotly.express as px
import plotly.graph_objects as go



df = pd.read_csv('../data/agg_prod_data.csv')
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


# Initialize the Dash app
app = Dash(__name__)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='Sephora Product Analysis'
)

PLOT_TEMPLATE_THEME = 'simple_white'
COLOUR_SCALE='plotly3_r'



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
)

max_price_filter = dbc.Input(
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


def normalize_colour_value(data_point, all_values):
    """
    Normalizes data point values for use with colour bar. 
    """
    return (data_point - min(all_values)) / (max(all_values) - min(all_values))


def joint_slope_scatter(df_product_pairs, df_base):

    slope_plot_title = "Unit Price Comparison Of Products"
    scatter_plot_title = "Explore Products By Size And Price"

    fig = sp.make_subplots(rows=1, cols=2, column_widths=[0.4, 0.6],
        subplot_titles=(slope_plot_title, scatter_plot_title))

    # slope plot - compare unit prices of related products
    tooltip_hover_template = '{}<br>{}<br>Size: {} oz.<br>Price: ${}<br>Category: {}<br>Mini-to-Standard Ratio: {:.2f}' 
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
            text=[tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a_mini'], row['price_mini'], row['lvl_2_cat_mini'], row['mini_to_standard_ratio']),
                  tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a_standard'], row['price_standard'], row['lvl_2_cat_standard'], row['mini_to_standard_ratio'])],
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
            range=[-0.2, 2 - 0.7],
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
        plot_bgcolor='white',
    )

    # right side - scatter plot
    marker_shapes = {'mini size':'circle', 'standard size':'square', 'refill size':'diamond', 'value size':'cross'}
    
    # grey markers, no mini-to-standard ratio
    df_no_ratio = df_base[df_base['mini_to_standard_ratio'].isna()]

    background_scatter = go.Scatter(
        x=df_no_ratio['amount_a'],
        y=df_no_ratio['price'],
        mode="markers",
        marker=dict(
            color=['grey' for x in range(df_no_ratio.shape[0])],
            symbol=[marker_shapes[row['swatch_group']] for i, row in df_no_ratio.iterrows()],
        ),
        opacity=0.6,
        hovertemplate='Size: %{x}oz.<br>Price: $%{y}, %{text}',
        text=[tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a'], row['price'], row['lvl_2_cat'], row['mini_to_standard_ratio']) for i, row in df_no_ratio.iterrows()]
    )

    fig.add_trace(background_scatter, row=1, col=2)

    df_w_ratio = df_base[df_base['mini_to_standard_ratio'].notnull()]
    scatter_highlight = go.Scatter(
        x=df_w_ratio['amount_a'],
        y=df_w_ratio['price'],
        mode="markers",
        marker=dict(
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
        hovertemplate='Size: %{x}oz.<br>Price: $%{y}, %{text}',
        text=[tooltip_hover_template.format(row['product_name'], row['brand_name'], row['amount_a'], row['price'], row['lvl_2_cat'], row['mini_to_standard_ratio']) for i, row in df_w_ratio.iterrows()],
    )

    fig.add_trace(scatter_highlight, row=1, col=2)
    
    fig.update_xaxes(title_text="Size (oz.)", row=1, col=2)
    fig.update_yaxes(title_text="Price ($)", row=1, col=2)

    return fig



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
                    dcc.Graph(
                        id='slope_scatter_joint',
                        figure=joint_slope_scatter(df_compare[50:70], df)
                    )
                ], width=12)
            ]),
        ], width=12),
    ]),
    # product details 
    dbc.Row([
        dbc.Col([
            # filters
            dbc.Row([
                dbc.Col(
                    id='product_info_filter',
                    children=[
                        dbc.InputGroup([
                            dbc.InputGroupText("Select Product"),
                            product_info_dropdown
                        ])
                    ],
                    width=3
                )
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

############# CALLBACKS ############# 

#need to add sorting option
# and update to plot titles  
@callback(
    Output('slope_scatter_joint','figure'),
    Input('product_category_l0_dropdown', 'value'),
    Input('brand_dropdown', 'value'),
    Input('max_price_filter', 'value'),
)
def update_joint_plot(category_val, brand_val, max_price_val):
    triggered_id = ctx.triggered_id
    df_filter_pairs = df_compare.copy()
    df_filter_products = df.copy()

    # need to update titles 
    # title = f'Explore{" "+brand_val.title() if brand_val else ""}{" "+category_val.title() if category_val else ""} Products By Size And Price'
    
    if category_val:
        df_filter_pairs = df_filter_pairs[df_filter_pairs['lvl_0_cat_standard']==category_val]
        df_filter_products = df_filter_products[df_filter_products['lvl_0_cat']==category_val]

    if brand_val:
        df_filter_pairs = df_filter_pairs[df_filter_pairs['brand_name']==brand_val]
        df_filter_products = df_filter_products[df_filter_products['brand_name']==brand_val]

    if max_price_val:
        df_filter_pairs = df_filter_pairs[df_filter_pairs['price_standard']<max_price_val]
        df_filter_products = df_filter_products[df_filter_products['price']<max_price_val]

    return joint_slope_scatter(df_filter_pairs, df_filter_products)
        
if __name__ == '__main__':
    app.run_server(debug=True)
