# import dash

from dash import Dash, html, dcc, Input, Output, callback

# import dash_core_components as dcc
# import dash_html_components as html
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

eligible_products = df[df['swatch_group'].isin(['standard size','mini size'])].groupby(['product_id'], as_index=False)['swatch_group'].count()
df = df.sort_values(by='amount_a',ascending=True)

eligible_products = df[df['swatch_group'].isin(['standard size','mini size'])].groupby(['product_id'], as_index=False)['swatch_group'].count()
eligible_products = eligible_products[eligible_products['swatch_group']==2]['product_id'].values
target_comp_df = df[(df['product_id'].isin(eligible_products)) & (df['swatch_group'].isin(['standard size','mini size']))]
target_comp_df['full_product'] = target_comp_df['brand_name']+' '+ target_comp_df['product_name']

target_comp_df = target_comp_df[target_comp_df.groupby(['brand_name','product_name'])['swatch_group'].transform(lambda x : x.nunique()>1)]


target_comp_df = target_comp_df.pivot(index=['brand_name','product_name'], columns='swatch_group', values='unit_price')
target_comp_df = target_comp_df.reset_index()
target_comp_df['size_diff'] = target_comp_df['standard size'] - target_comp_df['mini size']
target_comp_df = target_comp_df.set_index(['brand_name','product_name']).stack('swatch_group').reset_index().rename(columns={0:'unit_price'})

filtered_df = target_comp_df[(target_comp_df['swatch_group']!='size_diff') & (target_comp_df['brand_name']=='hourglass')]

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

# df = df[df['lvl_2_cat']=='Eyebrow']




# Initialize the Dash app
app = Dash(__name__)

# Define the layout of the app\
app.layout = html.Div([
    # Header section
    html.Div([
        html.H1('Sephora Savings Visualizer'),
        html.H3('subtitle.'),
    ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2'}),
    
    # First div with the scatterplot and filters
    html.Div([
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
    ], style={'padding': '20px'}),
    # Draw a pointplot to show pulse as a function of three categorical factors
# g = sns.catplot(
#     data=filtered_df, x="swatch_group", y="unit_price", hue="product_name",
#     capsize=.2, #palette="YlGnBu_d",
#     kind="point", height=6, aspect=.75,
# )
# g.despine(left=True)
    # Second div (empty)
    html.Div([
        dcc.Graph(
            id='pt_plot',
            figure=fig)
    ], style={'padding': '20px'}),
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
