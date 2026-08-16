from rental_processor import get_processed_rental_data
from transaction_processor import get_processed_transaction_data
from yield_calculator import calculate_yearly_yield

def main():
    print("--- Starting Pipeline ---")
    
    print("Processing Rental data and filling room types...")
    df_rent = get_processed_rental_data()
    
    print("Processing Transaction data...")
    df_trans = get_processed_transaction_data()
    
    print("Calculating Yearly Rental Yields...")
    final_report = calculate_yearly_yield(df_rent, df_trans)
    
    # Save results
    final_report.to_csv('dubai_market_yield_report.csv', index=False)
    print("Pipeline Complete. Results saved to 'dubai_market_yield_report.csv'")
    print(final_report.head(10))

if __name__ == "__main__":
    main()