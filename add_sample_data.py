"""
Script to add sample portfolio items to the database.
Run this script using: python manage.py shell < add_sample_data.py
"""

from portfolio.models import PortfolioItem

# Clear existing data
PortfolioItem.objects.all().delete()

print("Adding sample portfolio items...")

# Business Websites
portfolio_items = [
    PortfolioItem(
        title="Corporate Business Website",
        category="business",
        description="Professional website for a leading business consultancy firm with modern design and responsive layout.",
    ),
    PortfolioItem(
        title="Business Service Portal",
        category="business",
        description="Comprehensive business portal with service booking and customer management system.",
    ),
    PortfolioItem(
        title="Technology Company Website",
        category="business",
        description="Modern corporate website for a tech startup with interactive features and animations.",
    ),
    
    # E-Commerce Websites
    PortfolioItem(
        title="Fashion E-Commerce Store",
        category="ecommerce",
        description="Full-featured online clothing store with payment integration and inventory management.",
    ),
    PortfolioItem(
        title="Electronics Online Shop",
        category="ecommerce",
        description="E-commerce platform for electronics retailer with product reviews and ratings.",
    ),
    PortfolioItem(
        title="Grocery Delivery Platform",
        category="ecommerce",
        description="Online grocery ordering and delivery system with real-time tracking.",
    ),
    
    # Landing Pages
    PortfolioItem(
        title="Product Launch Landing Page",
        category="landing",
        description="High-converting landing page for new product launch with lead capture form.",
    ),
    PortfolioItem(
        title="Mobile App Landing Page",
        category="landing",
        description="Creative landing page for mobile app with download links and features showcase.",
    ),
    PortfolioItem(
        title="Event Promotion Page",
        category="landing",
        description="Engaging landing page for event promotion with registration and ticket booking.",
    ),
]

for item in portfolio_items:
    item.save()
    print(f"✓ Added: {item.title}")

print(f"\nSuccessfully added {len(portfolio_items)} portfolio items!")
print("You can now view them at: http://127.0.0.1:8000/portfolio/")
