# External Resources & References

This document lists the key external resources used for developing and maintaining the
CAWL payment module.

## 🔗 Official CAWL Documentation

### API Reference

- **URL**: https://docs.ecommerce.cawl-solutions.fr/fr/api-reference
- **Purpose**: Official API documentation for all CAWL endpoints
- **Key Sections**:
  - Create Hosted Checkout API
  - Payment Status API
  - Webhook Configuration
  - Error Codes and Responses

### Integration Guides

- **Hosted Checkout Guide**:
  https://docs.ecommerce.cawl-solutions.fr/fr/integration/basic-integration-methods/hosted-checkout-page
- **Purpose**: Step-by-step integration guide for hosted checkout
- **Key Features**:
  - Language localization (fr_FR, en_US, etc.)
  - Payment method pre-selection
  - Card grouping options
  - Payment attempt limits

### SDK Documentation

- **Python SDK**: https://docs.ecommerce.cawl-solutions.fr/fr/sdks-serveur/apercu
- **Purpose**: Official Python SDK for CAWL API integration
- **Key Components**:
  - Factory pattern for client creation
  - CommunicatorConfiguration setup
  - Request/response object models

## 🏗️ Odoo Reference Implementations

### Adyen Payment Module

- **URL**: https://github.com/odoo/odoo/tree/16.0/addons/payment_adyen
- **Purpose**: Reference implementation for Odoo payment modules
- **Key Patterns**:
  - Payment provider configuration
  - Transaction processing flow
  - Webhook handling
  - Error handling patterns

### Other Payment Modules

- **PayPal**: https://github.com/odoo/odoo/tree/16.0/addons/payment_paypal
- **Stripe**: https://github.com/odoo/odoo/tree/16.0/addons/payment_stripe
- **Purpose**: Additional reference implementations for different payment flows

## 📚 Development Resources

### Odoo Documentation

- **Developer refernce**: https://www.odoo.com/documentation/16.0/developer.html
- **Purpose**: Official Odoo developer docs
- **Key Topics**:
  - Framework references
  - Turorials and how-tos

### CAWL Merchant Portal

- **Purpose**: Merchant account management and configuration
- **Key Features**:
  - API credentials management
  - Webhook configuration
  - Payment method activation
  - Transaction monitoring

## 📋 Version Compatibility

### CAWL API Versions

- **Current**: v1 API (stable)
- **SDK Version**: onlinepayments-sdk-python3
- **Hosted Checkout**: Latest version with all features

### Odoo Compatibility

- **Target Version**: Odoo 16.0+
- **Payment Framework**: Compatible with current payment framework
- **Python Version**: 3.9+

## 🔄 Update Process

### Documentation Updates

- Update README.md with new features
- Modify RESOURCES.md for new references
- Update code comments for API changes
