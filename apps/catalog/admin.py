from django.contrib import admin
from .models import Brand, Category, Product, Variant, ProductImage, VariantAttribute, ProductCategory

class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductCategoryInline]

admin.site.register(Brand)
admin.site.register(Category)
admin.site.register(Product, ProductAdmin)
admin.site.register(Variant)
admin.site.register(ProductImage)
admin.site.register(VariantAttribute)