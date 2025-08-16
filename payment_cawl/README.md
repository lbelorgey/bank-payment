# CAWL Payment Module for Odoo

A comprehensive payment module for Odoo e-commerce that integrates with CAWL's hosted checkout solution.

## 🚀 Features

### Core Payment Integration

- **Hosted Checkout**: Secure payment processing through CAWL's hosted payment pages
- **Multi-Currency Support**: Supports 32+ currencies including EUR, USD, GBP, CHF, CAD, JPY, etc.
- **Automatic Order Confirmation**: Sales orders are automatically confirmed upon successful payment
- **Webhook Processing**: Real-time transaction status updates via webhooks
- **Payment Method Line Management**: Automatic creation and management of payment method lines

### Advanced Configuration

- **Environment Support**: Sandbox and Production environments
- **Product Filtering**: Restrict payment methods to specific CAWL products
- **Connection Testing**: Built-in API connection validation
- **Webhook Security**: Signature verification for webhook notifications
- **Journal Integration**: Proper accounting journal configuration

### Developer Features

- **Comprehensive Logging**: Detailed transaction and error logging
- **Error Handling**: Robust error handling with user-friendly messages
- **Cache Management**: Built-in cache clearing utilities
- **Testing Tools**: Standalone testing scripts for debugging

## 📁 Module Structure

```
addons/payment_cawl/
├── __init__.py
├── __manifest__.py
├── README.md
├── requirements.txt
├── controllers/
│   ├── __init__.py
│   └── controllers.py          # Webhook and return URL handling
├── data/
│   └── payment_method_data.xml # Payment method definitions
├── models/
│   ├── __init__.py
│   ├── payment_provider.py     # CAWL provider configuration
│   └── payment_transaction.py  # Transaction processing
├── security/
│   └── ir.model.access.csv    # Access rights
├── static/
│   ├── description/
│   │   └── card_icon.png      # Payment method icon
│   └── src/
│       ├── css/
│       │   └── payment_cawl.css
│       └── js/
│           └── payment_cawl.js # Frontend payment handling
└── views/
    ├── payment_cawl_templates.xml # Redirect form template
    └── payment_provider_views.xml # Provider configuration UI
```

## 🔧 Installation

### Prerequisites

- Odoo 16.0+
- Python 3.9+
- CAWL merchant account

### Dependencies

```bash
pip install onlinepayments-sdk-python3
```

### Module Installation

1. Copy the `payment_cawl` folder to your Odoo addons directory
2. Update the addons list in Odoo
3. Install the module via Apps menu
4. Configure CAWL provider in Payment Providers

## ⚙️ Configuration

### Required Fields

- **PSPID**: Your CAWL merchant ID
- **API Key**: CAWL API authentication key
- **API Secret**: CAWL API authentication secret
- **Webhook Key**: Webhook identification key
- **Webhook Secret**: Webhook signature verification secret
- **Server Environment**: Sandbox or Production

### Optional Features

- **Product Filtering**: Enable to restrict payment methods
- **Allowed Products**: Select specific CAWL payment products

## 🔄 Payment Flow

1. **Customer Checkout**: Customer selects CAWL payment method
2. **Session Creation**: Odoo creates CAWL hosted checkout session
3. **Redirect**: Customer is redirected to CAWL hosted checkout
4. **Payment Processing**: Customer completes payment on CAWL
5. **Return**: Customer returns to Odoo with payment result
6. **Webhook**: CAWL sends webhook with transaction status
7. **Order Confirmation**: Odoo automatically confirms sales order

## 🌐 Webhook Configuration

### Webhook URL

```
https://your-odoo-domain.com/payment/cawl/webhook
```

### Required Headers

- `Content-Type: application/json`
- `X-CAWL-Signature`: HMAC-SHA256 signature

### Webhook Payload Structure

```json
{
  "payment": {
    "id": "payment_id",
    "status": "PAID",
    "paymentOutput": {
      "references": {
        "merchantReference": "S00043"
      }
    }
  }
}
```

## 🛠️ Development

### Cache Clearing

Use the provided `clear_cache.sh` script to clear Odoo caches during development:

```bash
./clear_cache.sh
```

### Testing

- **Connection Test**: Use the "Test Connection" button in provider configuration
- **Manual Status Update**: Use `/payment/cawl/update_status/<tx_id>?status=PAID`
- **Webhook Testing**: Use `/payment/cawl/test_webhook` for webhook accessibility testing

### Debugging

- Check Odoo logs for detailed transaction information
- Use browser console for frontend debugging
- Monitor webhook logs for notification processing

## 📊 Supported Status Values

| CAWL Status          | Odoo State | Description        |
| -------------------- | ---------- | ------------------ |
| `PAID`               | `done`     | Payment successful |
| `CAPTURED`           | `done`     | Payment captured   |
| `PENDING_CAPTURE`    | `done`     | Payment authorized |
| `PENDING_PAYMENT`    | `pending`  | Payment processing |
| `PENDING_COMPLETION` | `pending`  | Payment pending    |
| `CREATED`            | `pending`  | Payment created    |
| `CANCELLED`          | `cancel`   | Payment cancelled  |
| `REJECTED`           | `error`    | Payment rejected   |

## 🔒 Security Features

- **HMAC Signature Verification**: Webhook signature validation
- **Environment Isolation**: Separate sandbox/production configurations
- **Credential Encryption**: Sensitive fields stored securely
- **Access Control**: Proper Odoo access rights configuration

## 🚨 Troubleshooting

### Debug Commands

```bash
# Check module status
docker compose exec web odoo shell -d odoo -c /etc/odoo/odoo.conf

# View logs
docker compose logs web --follow

# Clear cache - LOCAL DEV ONLY
./clear_cache.sh
```

## 📈 Performance

- **Connection Pooling**: Configured with max_connections=10
- **Timeout Settings**: 30s connect, 60s socket timeout
- **Caching**: Proper Odoo cache management
- **Async Processing**: Non-blocking webhook processing

## 📄 License

This module is provided as-is for integration with CAWL payment services. Ensure compliance with CAWL's terms of service and Odoo's licensing requirements.
