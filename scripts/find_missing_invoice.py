"""Find the missing invoice 13304 for lot 20-3927 in the Bovina PDF."""
import fitz
from pathlib import Path

PDF_PATH = Path(r"C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Bovina.pdf")


def main():
    with fitz.open(PDF_PATH) as doc:
        print(f"Total pages: {doc.page_count}")
        print()
        
        statement_pages = []
        invoice_pages = []
        unclassified = []
        
        for i in range(doc.page_count):
            text = doc.load_page(i).get_text("text").lower()
            
            is_statement = "statement of notes" in text
            is_invoice = "feed invoice" in text
            has_3927 = "20-3927" in text
            has_13304 = "13304" in text
            
            if is_statement:
                statement_pages.append(i)
            elif is_invoice:
                invoice_pages.append(i)
            else:
                unclassified.append(i)
            
            if has_3927 or has_13304:
                print(f"Page {i}: 20-3927={has_3927}, 13304={has_13304}, statement={is_statement}, invoice={is_invoice}")
        
        print(f"\nStatement pages: {statement_pages}")
        print(f"Invoice pages: {invoice_pages}")
        print(f"Unclassified pages: {unclassified}")
        
        # Check unclassified pages
        print("\n--- Unclassified page contents ---")
        for i in unclassified:
            text = doc.load_page(i).get_text("text")
            print(f"\nPage {i}:")
            print(text[:800])
            print("...")


if __name__ == "__main__":
    main()
