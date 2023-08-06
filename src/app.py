from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

df_products = pd.read_csv('../data/processed_prod_data.csv')

df = df_products.groupby(['product_id','product_name', 'brand_name', 'swatch_group','amount_a'], as_index=False).agg({
    'price':'max',
    'internal_product_id':'nunique',
    'rating':'max',
    'product_reviews':'max',
    'n_loves':'max',
    'lvl_0_cat':'first',
    'lvl_1_cat':'first',
    'lvl_2_cat':'first',
    'sku':'unique',
    'amount_b':'first',
    'unit_b':'first',
    'product_multiplier':'first'
})

df['amount_a_adjusted'] = df['amount_a'] * df['product_multiplier'].astype('float')
df['unit_price'] = df['price']/df['amount_a_adjusted']


eligible_products = df[df['swatch_group'].isin(['standard size','mini size'])].groupby(['product_id'], as_index=False)['swatch_group'].count()
eligible_products = eligible_products[eligible_products['swatch_group']==2]['product_id'].values
target_comp_df = df[(df['product_id'].isin(eligible_products)) & (df['swatch_group'].isin(['standard size','mini size']))]
target_comp_df['full_product'] = target_comp_df['brand_name']+' '+ target_comp_df['product_name']

target_comp_df = target_comp_df[target_comp_df.groupby(['brand_name','product_name'])['swatch_group'].transform(lambda x : x.nunique()>1)]

target_comp_df = target_comp_df.pivot(index=['brand_name','product_name'], columns='swatch_group', values='unit_price')
target_comp_df = target_comp_df.reset_index()
target_comp_df['size_diff'] = target_comp_df['standard size'] - target_comp_df['mini size']
target_comp_df['ratio_mini_to_standard'] = target_comp_df['mini size'] / target_comp_df['standard size']

fig_hist = px.histogram(target_comp_df, x="ratio_mini_to_standard")

target_comp_df = target_comp_df.set_index(['brand_name','product_name']).stack('swatch_group').reset_index().rename(columns={0:'unit_price'})
target_comp_df = target_comp_df[target_comp_df.groupby(['brand_name','product_name'])['swatch_group'].transform(lambda x : x.nunique()>1)]
filtered_df = target_comp_df[(~target_comp_df['swatch_group'].isin(['size_diff','ratio_mini_to_standard'])) & (target_comp_df['brand_name']=='hourglass')]

fig = px.line(
                filtered_df,
                y="unit_price",
                x="swatch_group",
                color="product_name",
                template="simple_white",
                markers=True
                )

fig.update_xaxes({'autorange': False})

dropdown_options = {x:x for x in df['lvl_0_cat'].unique() if x!=' '}





# Initialize the Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.LUX], suppress_callback_exceptions=True)
# Define the layout of the app\
app.layout = html.Div([
    # Header section
    dbc.Row([
        html.H1('Sephora Savings Visualizer'),
        html.H3('subtitle.'),
    ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2'}),
    dbc.Row([
        dbc.Row([
            dbc.Col([
                dcc.Input(id='range', type='number', min=5, max=20, step=5)
            ], width=3)
        ]),
        dbc.Row([
            dbc.Col([
                html.Div([
                    dcc.Graph(
                        id='pt_plot',
                        figure=fig)
                    ]),
                ], width=6),
            dbc.Col([
                html.Div([
                    dcc.Graph(
                        id='ratio_unit_price_hist',
                        figure=fig_hist
                    )
                ]),
            ], width=6)
        ])
    ]),
        
    
    # First div with the scatterplot and filters
    dbc.Row([
        dbc.Col([
        dcc.Dropdown(
            options=dropdown_options,
            value=next(iter(dropdown_options)),
            id='crossfilter-dataframe',
            ),
        dcc.Graph(
            id='scatterplot',
            figure=px.scatter(
                df,
                x='amount_a',
                y='price',
                color='swatch_group',
                hover_data=['brand_name', 'product_name'],
                labels={ # replaces default labels by column name
                    'amount_a': "Product Size (oz*)",  'price': "Price (CAD)", "swatch_group": "Size Category"
                },
                template="simple_white"
            ),
        ),
        # Add filters or any other controls here
        # For example: dcc.Dropdown, dcc.RangeSlider, etc.
    ], style={'padding': '20px'})])

])
@callback(
    Output('scatterplot', 'figure'),
    Input('crossfilter-dataframe', 'value'))
def update_graph(value):
    dff = df[df['lvl_0_cat'] == value]

    
    fig = px.scatter(
        dff,
        x='amount_a',
        y='price',
        color='swatch_group',
        hover_data=['brand_name', 'product_name'],
        labels={ # replaces default labels by column name
            'amount_a': "Product Size (oz.)*",  'price': "Price (CAD)", "swatch_group": "Size Category"
        },
        template="simple_white")
    return fig


# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
