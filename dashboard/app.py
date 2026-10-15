from pathlib import Path
import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='PeriodWise | Analytics', page_icon='🌸', layout='wide')

st.markdown('''<style>
.block-container {padding-top:1.5rem; max-width:1400px;}
[data-testid="stMetric"] {background:#f8f5fb; border:1px solid #ece5f2; padding:14px; border-radius:14px;}
</style>''', unsafe_allow_html=True)

from database import load_data as load_database_data
st.sidebar.success("Data Source: PostgreSQL")

@st.cache_data(ttl=300, show_spinner=False)
def load_data(folder=None):
    sales, products, prices, survey = load_database_data()

    return {
        "sales": sales,
        "products": products,
        "prices": prices,
        "survey": survey
    }


def download_csv(df, filename, label='Download CSV'):
    st.download_button(label, data=df.to_csv(index=False).encode('utf-8-sig'),
                       file_name=filename, mime='text/csv')


def category_chart(df, col, title, horizontal=True):
    counts = df[col].dropna().astype(str).value_counts().rename_axis(col).reset_index(name='Count')
    if counts.empty:
        st.info('No records for this chart.')
        return
    if horizontal:
        fig = px.bar(counts.sort_values('Count'), x='Count', y=col, orientation='h', title=title)
    else:
        fig = px.bar(counts, x=col, y='Count', title=title)
    st.plotly_chart(fig, use_container_width=True)


def multiselect_counts(series):
    return (series.dropna().astype(str).str.split(',').explode().str.strip()
            .loc[lambda s: s.ne('')].value_counts())

st.title('🌸 PeriodWise')
st.caption('Menstrual product sales, pricing, product characteristics & consumer preferences')

try:
   data = load_data()
except (FileNotFoundError, PermissionError, pd.errors.EmptyDataError) as exc:
    st.error(f'Unable to load cleaned CSV files from: {DATA_DIR}')
    st.code(str(exc))
    st.info('Place app.py in your dashboard folder and keep the four cleaned CSV files in data/processed. You can also set PERIODWISE_DATA_DIR to the processed-data folder.')
    st.stop()

sales, products, prices, survey = (data[k].copy() for k in ('sales', 'products', 'prices', 'survey'))
for col in ['Units_Sold', 'Sales_Value']:
    sales[col] = pd.to_numeric(sales[col], errors='coerce')
for col in ['Selling_Price', 'MRP', 'Discount_Percent', 'Price_Per_Unit']:
    prices[col] = pd.to_numeric(prices[col], errors='coerce')
for col in ['Price_Importance', 'Product_Satisfaction']:
    for col in ['Price_Importance', 'Product_Satisfaction']:
        if col in survey.columns:
            survey[col] = pd.to_numeric(survey[col], errors='coerce')
if products['Product_ID'].duplicated().any():
    st.error('Duplicate Product_ID values in product catalog; cannot safely merge prices.')
    st.stop()
joined = prices.merge(products[['Product_ID', 'Product_Type', 'Brand', 'Reusable']],
                      on='Product_ID', how='left', validate='many_to_one')

page = st.sidebar.radio('Explore', ['Overview', 'Sales Analytics', 'Product Analytics', 'Pricing Analytics', 'Survey Analytics'])
st.sidebar.caption('Data source: cleaned local CSV files')
st.sidebar.caption('Retail observations and survey responses are samples, not market-wide estimates.')

if page == 'Overview':
    st.subheader('Project overview')
    a, b, c, d = st.columns(4)
    a.metric('Sales records', f'{len(sales):,}')
    b.metric('Catalog products', f'{len(products):,}')
    c.metric('Price observations', f'{len(prices):,}')
    d.metric('Survey respondents', f'{int(survey.loc[survey['Metric'] == 'Responses', 'Count'].iloc[0]):,}')
    l, r = st.columns(2)
    with l:
        category_chart(products, 'Product_Type', 'Catalog product types')
    with r:
        category_chart(prices, 'Retailer', 'Retail price observations')
    st.info('Sales records cover government Jan Aushadhi Suvidha reporting periods; catalog and retailer data are separate observational sources. Do not combine them into one sales total.')

elif page == 'Sales Analytics':
    st.subheader('Government sales analytics')
    years = sorted(sales['Financial_Year'].dropna().astype(str).unique().tolist())
    periods = sorted(sales['Reporting_Period'].dropna().astype(str).unique().tolist())
    year_filter = st.multiselect('Financial year', years, default=years)
    period_filter = st.multiselect('Reporting period', periods, default=periods)
    filtered = sales[sales['Financial_Year'].astype(str).isin(year_filter) &
                     sales['Reporting_Period'].astype(str).isin(period_filter)]
    a, b, c = st.columns(3)
    a.metric('Records', len(filtered))
    b.metric('Recorded units sold', f"{filtered['Units_Sold'].sum():,.0f}")
    c.metric('Rows with sales value', int(filtered['Sales_Value'].notna().sum()))
    state = (filtered.groupby('State', as_index=False)['Units_Sold'].sum()
             .sort_values('Units_Sold', ascending=False).head(15))
    if not state.empty:
        st.plotly_chart(px.bar(state.sort_values('Units_Sold'), x='Units_Sold', y='State',
                               orientation='h', title='Top states by recorded units sold'), use_container_width=True)
    fy = filtered.groupby(['Financial_Year', 'Reporting_Period'], as_index=False)['Units_Sold'].sum()
    if not fy.empty:
        st.plotly_chart(px.bar(fy, x='Financial_Year', y='Units_Sold', color='Reporting_Period',
                               barmode='group', title='Recorded units by financial year and reporting period'), use_container_width=True)
    st.warning('Reporting periods may cover different durations. These totals are descriptive and should not be interpreted as directly comparable annual growth. Missing sales values remain missing.')
    st.dataframe(filtered, use_container_width=True)
    download_csv(filtered, 'periodwise_filtered_sales.csv')

elif page == 'Product Analytics':
    st.subheader('Product catalog analytics')
    types = sorted(products['Product_Type'].dropna().unique().tolist())
    chosen = st.multiselect('Product types', types, default=types)
    filtered = products[products['Product_Type'].isin(chosen)]
    a, b, c = st.columns(3)
    a.metric('Catalog listings', len(filtered))
    b.metric('Brands represented', filtered['Brand'].nunique())
    c.metric('Product types', filtered['Product_Type'].nunique())
    l, r = st.columns(2)
    with l:
        category_chart(filtered, 'Product_Type', 'Products by type')
    with r:
        category_chart(filtered, 'Brand', 'Brands in selected catalog')
    if 'Reusable' in filtered:
        category_chart(filtered, 'Reusable', 'Recorded reusable classifications')
    st.caption('Counts describe collected product listings, not sales volume or market share. Missing feature fields may be inapplicable or unavailable.')
    st.dataframe(filtered, use_container_width=True)
    download_csv(filtered, 'periodwise_filtered_products.csv')

elif page == 'Pricing Analytics':
    st.subheader('Retail pricing analytics')
    retailers = sorted(joined['Retailer'].dropna().unique().tolist())
    types = sorted(joined['Product_Type'].dropna().unique().tolist())
    c1, c2 = st.columns(2)
    selected_retailers = c1.multiselect('Retailers', retailers, default=retailers)
    selected_types = c2.multiselect('Product types', types, default=types)
    filtered = joined[joined['Retailer'].isin(selected_retailers) & joined['Product_Type'].isin(selected_types)]
    a, b, c = st.columns(3)
    a.metric('Price observations', len(filtered))
    a_median = filtered['Selling_Price'].median()
    b.metric('Median selling price', f'₹{a_median:,.2f}' if pd.notna(a_median) else 'N/A')
    c.metric('Recorded discounts', int(filtered['Discount_Percent'].notna().sum()))
    if not filtered.empty:
        st.plotly_chart(px.box(filtered, x='Product_Type', y='Selling_Price', color='Retailer',
                               title='Selling price by product type'), use_container_width=True)
        unit_data = filtered.dropna(subset=['Price_Per_Unit'])
        if not unit_data.empty:
            st.plotly_chart(px.box(unit_data, x='Product_Type', y='Price_Per_Unit',
                                   title='Price per unit by product type'), use_container_width=True)
        discounts = filtered.dropna(subset=['Discount_Percent'])
        if not discounts.empty:
            st.plotly_chart(px.histogram(discounts, x='Discount_Percent', nbins=20,
                                         title='Recorded discount distribution'), use_container_width=True)
    st.warning('Retailers may have different sampled product mixes. Unit prices across reusable and disposable types are not equivalent. Missing MRP/discount is not a zero discount.')
    st.dataframe(filtered, use_container_width=True)
    download_csv(filtered, 'periodwise_filtered_prices.csv')


elif page == 'Survey Analytics':
    st.subheader('Consumer survey analytics')

    st.caption(
        'Overall results from 69 survey respondents. '
        'Individual survey responses are not displayed.'
    )

    def get_metric_rows(metric):
        return survey[survey['Metric'] == metric].copy()

    def show_summary_chart(metric, title):
        chart_data = get_metric_rows(metric)

        if chart_data.empty:
            st.info(f'No data available for {title}')
            return

        fig = px.bar(
            chart_data,
            x='Category',
            y='Count',
            title=title,
            text='Count'
        )

        st.plotly_chart(fig, use_container_width=True)

    def get_average(metric):
        rows = get_metric_rows(metric)

        if rows.empty:
            return None

        count = rows['Count'].iloc[0]
        total = rows['Sum'].iloc[0]

        if pd.isna(count) or count == 0:
            return None

        return total / count

    response_rows = get_metric_rows('Responses')
    total_responses = (
        int(response_rows['Count'].iloc[0])
        if not response_rows.empty else 0
    )

    price_avg = get_average('Price_Importance')
    satisfaction_avg = get_average('Product_Satisfaction')

    a, b, c = st.columns(3)

    a.metric('Responses', total_responses)

    b.metric(
        'Avg. price importance (1–5)',
        f'{price_avg:.2f}' if price_avg is not None else 'N/A'
    )

    c.metric(
        'Avg. satisfaction (1–5)',
        f'{satisfaction_avg:.2f}'
        if satisfaction_avg is not None else 'N/A'
    )

    l, r = st.columns(2)

    with l:
        show_summary_chart(
            'Monthly_Spending',
            'Reported monthly spending'
        )

        show_summary_chart(
            'Primary_Product',
            'Primary product used'
        )

    with r:
        show_summary_chart(
            'Switched_Due_To_Price',
            'Switched due to price'
        )

        show_summary_chart(
            'Reusable_Willingness',
            'Willingness to use reusable products'
        )

    st.warning(
        'Convenience sample (69 respondents), concentrated among '
        'young students. Results are not representative of '
        'the national population.'
    )

    st.caption(
        'Categories with fewer than five responses have been '
        'combined into Other / Not disclosed.'
    )
