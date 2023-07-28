import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.express as px


df_products = pd.read_csv('../data/processed_prod_data.csv')
df_products[['url_path','product_id']] = df_products['url_path'].str.split("-P",expand=True)

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
    'unit_b':'first'
})

df['unit_price'] = df['price']/df['amount_a']


df = df[df['lvl_2_cat']=='Eyebrow']


# Initialize the Dash app
app = dash.Dash(__name__)

# Define the layout of the app\
app.layout = html.Div([
    # Header section
    html.Div([
        html.H1('Sephora Savings Visualizer'),
        html.H3('subtitle.'),
    ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2'}),
    
    # First div with the scatterplot and filters
    html.Div([
        dcc.Graph(
            id='scatterplot',
            figure=px.scatter(df, x='amount_a', y='price', color='swatch_group', hover_data=['brand_name', 'product_name'])
        ),
        # Add filters or any other controls here
        # For example: dcc.Dropdown, dcc.RangeSlider, etc.
    ], style={'padding': '20px'}),
    
    # Second div (empty)
    html.Div([], style={'padding': '20px'}),
])

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
