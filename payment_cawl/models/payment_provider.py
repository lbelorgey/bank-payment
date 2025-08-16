# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Check CAWL SDK availability
try:
    import onlinepayments
    CAWL_SDK_AVAILABLE = True
except ImportError:
    CAWL_SDK_AVAILABLE = False
    _logger.warning("CAWL SDK not available. Please install: pip install onlinepayments-sdk-python3")



class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('cawl', 'CAWL')],
        ondelete={'cawl': 'set default'}
    )

    # CAWL specific fields
    cawl_pspid = fields.Char(
        string="PSPID",
        help="CAWL PSPID (Payment Service Provider ID) from your CAWL account",
        required_if_provider='cawl',
        groups='base.group_system'
    )
    cawl_api_key = fields.Char(
        string="CAWL API Key",
        help="CAWL API Key for authentication",
        required_if_provider='cawl',
        groups='base.group_system'
    )
    cawl_api_secret = fields.Char(
        string="CAWL API Secret",
        help="CAWL API Secret for authentication",
        required_if_provider='cawl',
        groups='base.group_system'
    )
    cawl_webhook_key = fields.Char(
        string="Webhook Key",
        help="CAWL Webhook Key for identification",
        groups='base.group_system'
    )


    # Webhook secret for signature verification
    cawl_webhook_secret = fields.Char(
        string='Webhook Secret',
        help='Secret key for verifying webhook signatures from CAWL',
        required=False
    )

    # Server environment selection
    cawl_server_url = fields.Selection([
        ('sandbox', 'Sandbox (Test)'),
        ('production', 'Production')
    ], string="Server Environment",
       help="Select the CAWL environment (sandbox or production)",
       default='sandbox',
       required_if_provider='cawl')

    # Product configuration fields
    cawl_allowed_product_ids = fields.Many2many(
        'cawl.payment.product',
        string="Allowed Payment Products",
        help="Select which payment products to show in hosted checkout. Leave empty to show all available products."
    )
    cawl_use_product_filter = fields.Boolean(
        string="Filter Payment Products",
        help="Enable to restrict payment methods to selected products only",
        default=False
    )

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override to filter CAWL availability based on currency """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        cawl_providers = providers.filtered(lambda p: p.code == 'cawl')
        if not cawl_providers:
            return providers

        # Filter based on supported currencies
        if currency_id:
            currency = self.env['res.currency'].browse(currency_id)
            if currency.name not in self._get_cawl_supported_currencies():
                providers = providers - cawl_providers

        return providers

    def _get_cawl_supported_currencies(self):
        """ Return list of currencies supported by CAWL """
        return [
            'EUR', 'USD', 'GBP', 'CHF', 'CAD', 'JPY', 'AUD', 'NZD',
            'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'BGN', 'RON',
            'HRK', 'ISK', 'TRY', 'ILS', 'ZAR', 'BRL', 'MXN', 'SGD',
            'HKD', 'CNY', 'INR', 'KRW', 'THB', 'MYR', 'PHP', 'IDR'
        ]

    def _compute_feature_support_fields(self):
        """ Define which features are supported by CAWL """
        super()._compute_feature_support_fields()
        cawl_providers = self.filtered(lambda p: p.code == 'cawl')
        cawl_providers.support_manual_capture = True
        cawl_providers.support_refund = 'partial'  # CAWL supports partial refunds (like Stripe)
        cawl_providers.support_tokenization = False  # Hosted checkout doesn't support tokenization

    @api.constrains('state')
    def _check_cawl_configuration(self):
        cawl_providers = self.filtered(lambda p: p.code == 'cawl' and p.state != 'disabled')
        for provider in cawl_providers:
            if not provider.cawl_server_url:
                raise ValidationError(_("Server URL is required for CAWL provider."))
            if not provider.cawl_pspid:
                raise ValidationError(_("Merchant ID is required for CAWL provider."))
            if not provider.cawl_api_key:
                raise ValidationError(_("API Key is required for CAWL provider."))
            if not provider.cawl_api_secret:
                raise ValidationError(_("API Secret is required for CAWL provider."))
            if not provider.cawl_webhook_key:
                raise ValidationError(_("Webhook Key is required for CAWL provider."))
            if not provider.cawl_webhook_secret:
                raise ValidationError(_("Webhook Secret is required for CAWL provider."))

    def _get_default_payment_method_codes(self):
        """ Return the default payment method codes """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'cawl':
            return default_codes
        # Return the 'cawl' payment method like Stripe returns 'stripe'
        return ['cawl']

    def _get_supported_currencies(self):
        """ Return supported currencies for CAWL """
        supported_currencies = super()._get_supported_currencies()
        if self.code != 'cawl':
            return supported_currencies

        return self.env['res.currency'].search([
            ('name', 'in', self._get_cawl_supported_currencies())
        ])

    def _cawl_get_api_url(self):
        """ Get the CAWL API URL based on environment. """
        if self.cawl_server_url == 'production':
            return 'https://payment.cawl-solutions.fr'
        else:
            return 'https://payment.preprod.cawl-solutions.fr'

    def _get_cawl_client(self):
        """ Get configured CAWL SDK client. """
        # Get API configuration based on environment
        api_endpoint = self._cawl_get_api_url()

        # Create client configuration
        from onlinepayments.sdk.factory import Factory
        from onlinepayments.sdk.communicator_configuration import CommunicatorConfiguration

        config = CommunicatorConfiguration(
            api_endpoint=api_endpoint,
            api_key_id=self.cawl_api_key,
            secret_api_key=self.cawl_api_secret,
            authorization_type='v1HMAC',
            integrator='Odoo-CAWL-Integration',
            connect_timeout=30,
            socket_timeout=60,
            max_connections=10
        )

        return Factory.create_client_from_configuration(config)

    def action_test_cawl_connection(self):
        """ Test CAWL API connection """
        self.ensure_one()

        if not CAWL_SDK_AVAILABLE:
            raise UserError(_(
                "CAWL SDK is not installed. Please install it using:\n"
                "pip install onlinepayments-sdk-python3\n"
                "Then restart the Odoo server."
            ))

        # Validate credentials are configured
        if not all([self.cawl_pspid, self.cawl_api_key, self.cawl_api_secret]):
            raise UserError(_(
                "Please configure all CAWL credentials first:\n"
                "• PSPID (Merchant ID)\n"
                "• API Key\n"
                "• API Secret"
            ))

        try:
            # Test the actual CAWL API connection
            success, message = self._test_cawl_api_connection()

            if success:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('✅ Connection Test Successful'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_("Connection test failed: %s") % message)

        except Exception as e:
            error_msg = self._parse_connection_error(str(e))
            raise UserError(_("Connection test failed: %s") % error_msg)

    def _test_cawl_api_connection(self):
        """ Perform the actual CAWL API connection test """
        try:
            # Import CAWL SDK components
            from onlinepayments.sdk.factory import Factory
            from onlinepayments.sdk.communicator_configuration import CommunicatorConfiguration

            # Get API configuration
            api_endpoint = self._cawl_get_api_url()

            # Validate all required fields
            if not api_endpoint:
                return False, _("API endpoint is missing")
            if not self.cawl_api_key:
                return False, _("API key is required")
            if not self.cawl_api_secret:
                return False, _("API secret is required")

            _logger.info("Configuration values - endpoint: %s, api_key: %s, merchant_id: %s",
                        api_endpoint, self.cawl_api_key[:8] + "...", self.cawl_pspid)

            # Use centralized client method
            client = self._get_cawl_client()

            # Test by making a simpler API call that requires authentication
            try:
                # Validate configuration values first
                if not self.cawl_pspid:
                    return False, _("Merchant ID is required for connection test")

                # Ensure merchant_id is a string
                merchant_id_str = str(self.cawl_pspid).strip()
                if not merchant_id_str:
                    return False, _("Merchant ID cannot be empty")

                _logger.info("Using merchant ID: '%s'", merchant_id_str)

                # Try to make a simpler API call - just get payment methods
                # This requires authentication but is much simpler than creating hosted checkout
                _logger.info("Creating merchant client for: %s", merchant_id_str)
                merchant_client = client.merchant(merchant_id_str)

                _logger.info("Testing API access with minimal hosted checkout...")

                # Create hosted checkout client
                hosted_checkout_client = merchant_client.hosted_checkout()
                _logger.info("Hosted checkout client created successfully!")

                # Test with actual hosted checkout API call
                try:
                    from onlinepayments.sdk.domain.create_hosted_checkout_request import CreateHostedCheckoutRequest
                    from onlinepayments.sdk.domain.hosted_checkout_specific_input import HostedCheckoutSpecificInput
                    from onlinepayments.sdk.domain.order import Order
                    from onlinepayments.sdk.domain.amount_of_money import AmountOfMoney

                    _logger.info("Creating minimal test request...")

                    # Create minimal test request
                    request = CreateHostedCheckoutRequest()

                    # Hosted checkout input
                    hosted_input = HostedCheckoutSpecificInput()
                    hosted_input.locale = "en_US"
                    hosted_input.return_url = "https://test.local/connection-test"
                    request.hosted_checkout_specific_input = hosted_input

                    # Order with minimal amount
                    order = Order()
                    amount = AmountOfMoney()
                    amount.amount = 100  # 1.00 EUR in cents
                    amount.currency_code = "EUR"
                    order.amount_of_money = amount
                    request.order = order

                    _logger.info("Making test API call to CAWL servers...")

                    # Make the actual API call - this is the real test
                    response = hosted_checkout_client.create_hosted_checkout(request)

                    _logger.info("Connection test successful! Checkout ID: %s", response.hosted_checkout_id)

                    return True, _(
                        "Connection successful! ✅\n"
                        "• Merchant ID: %s\n"
                        "• Environment: %s\n"
                        "• API Endpoint: %s\n"
                        "• Test Checkout ID: %s\n"
                        "• All services operational"
                    ) % (merchant_id_str, self.cawl_server_url, api_endpoint, response.hosted_checkout_id)

                except Exception as checkout_error:
                    _logger.error("Connection test failed: %s", str(checkout_error))

                    # Map specific errors to clear messages
                    error_str = str(checkout_error).lower()
                    if ("9007" in str(checkout_error) or "access_to_merchant_not_allowed" in error_str):
                        return False, _("Merchant access denied - verify your merchant ID and API key permissions")
                    elif ("401" in error_str or "unauthorized" in error_str or "authentication" in error_str):
                        return False, _("Authentication failed - check your API credentials")
                    elif ("403" in error_str or "forbidden" in error_str):
                        return False, _("Access forbidden - verify API permissions and merchant configuration")
                    elif ("404" in error_str or "not found" in error_str):
                        return False, _("Merchant ID not found - check your PSPID for the selected environment")
                    elif ("timeout" in error_str or "connection" in error_str):
                        return False, _("Connection timeout - check network connectivity")
                    else:
                        return False, _("Connection failed: %s") % str(checkout_error)

            except Exception as api_error:
                # Log the specific error for debugging
                _logger.error("CAWL connection test failed: %s", str(api_error))

                # Check for specific error types
                error_str = str(api_error).lower()
                if "401" in error_str or "unauthorized" in error_str or "authentication" in error_str:
                    return False, _("Authentication failed - check your API credentials and environment setting")
                elif "404" in error_str or "not found" in error_str:
                    return False, _("Merchant ID not found - check your PSPID is correct for the selected environment")
                elif "403" in error_str or "forbidden" in error_str:
                    return False, _("Access forbidden - check your API permissions and merchant configuration")
                elif "timeout" in error_str or "connection" in error_str:
                    return False, _("Connection timeout - check your internet connection and firewall settings")
                else:
                    return False, _("API Error: %s") % str(api_error)

        except ImportError as e:
            _logger.error("CAWL SDK import failed: %s", str(e))
            return False, _("CAWL SDK not available - please install: pip install onlinepayments-sdk-python3")
        except Exception as e:
            import traceback
            _logger.error("CAWL connection test failed with exception: %s", str(e))
            _logger.error("Full traceback: %s", traceback.format_exc())

            # Return more detailed error for debugging
            return False, _("Connection test failed: %s\n\nFor debugging, check the server logs for full details.") % str(e)

    def _parse_connection_error(self, error_string):
        """ Parse connection errors and provide user-friendly messages """
        error_lower = error_string.lower()

        if "unauthorized" in error_lower or "authentication" in error_lower:
            return _(
                "Authentication failed. Please check:\n"
                "• API Key is correct\n"
                "• API Secret is correct\n"
                "• Credentials match the selected environment (sandbox/production)"
            )
        elif "not found" in error_lower or "404" in error_lower:
            return _(
                "Merchant not found. Please check:\n"
                "• PSPID (Merchant ID) is correct\n"
                "• Merchant is active in CAWL dashboard\n"
                "• Environment setting matches your CAWL account"
            )
        elif "connection" in error_lower or "timeout" in error_lower or "network" in error_lower:
            return _(
                "Network connection failed. Please check:\n"
                "• Internet connection is working\n"
                "• Firewall allows outbound HTTPS connections\n"
                "• CAWL servers are accessible"
            )
        elif "ssl" in error_lower or "certificate" in error_lower:
            return _(
                "SSL/Certificate error. Please check:\n"
                "• System date and time are correct\n"
                "• SSL certificates are up to date\n"
                "• Network proxy settings if applicable"
            )
        else:
            return error_string

    def _get_redirect_form_view(self, is_validation=False):
        """ Return the view of the template used to render the redirect form.

        For CAWL hosted checkout, we use a simple redirect template.
        """
        return self.env.ref('payment_cawl.redirect_form')

    def _should_build_inline_form(self, is_validation=False):
        """ Return whether the inline payment form should be instantiated.

        For CAWL hosted checkout, we always use redirect, so return False.
        """
        return False

    def _validate_webhook_credentials(self):
        """ Validate webhook credentials using CAWL API """
        try:
            import requests
            import base64

            # Prepare the validation request
            validation_data = {
                "key": self.cawl_webhook_key,
                "secret": self._calculate_webhook_secret_hash()
            }

            # Make API call to validate credentials
            url = f"{self.cawl_server_url}/v1/{self.cawl_pspid}/webhooks/validate-credentials"

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Basic {base64.b64encode(f"{self.cawl_api_key}:{self.cawl_api_secret}".encode()).decode()}'
            }

            response = requests.post(url, json=validation_data, headers=headers, timeout=30)

            if response.status_code == 200:
                _logger.info("Webhook credentials validated successfully for provider %s", self.name)
                return True
            else:
                _logger.error("Webhook credentials validation failed for provider %s: %s", self.name, response.text)
                return False

        except Exception as e:
            _logger.error("Error validating webhook credentials for provider %s: %s", self.name, str(e))
            return False

    def _calculate_webhook_secret_hash(self):
        """ Calculate base64 encoded hash of empty string using webhook secret """
        try:
            import base64
            import hmac
            import hashlib

            # Create HMAC-SHA256 of empty string using webhook secret
            hmac_obj = hmac.new(
                self.cawl_webhook_secret.encode('utf-8'),
                b'',  # empty string
                hashlib.sha256
            )

            # Return base64 encoded digest
            return base64.b64encode(hmac_obj.digest()).decode('utf-8')

        except Exception as e:
            _logger.error("Error calculating webhook secret hash: %s", str(e))
            return ""

    def action_sync_payment_products(self):
        """ Sync payment products from CAWL API """
        self.ensure_one()
        if self.code != 'cawl':
            return

        try:
            products = self._fetch_cawl_payment_products()
            self._sync_payment_products(products)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Payment products synchronized successfully'),
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error("Error syncing payment products: %s", str(e))
            raise UserError(_("Failed to sync payment products: %s") % str(e))

    def _fetch_cawl_payment_products(self):
        """ Fetch available payment products from CAWL API using SDK """
        try:
            # Use CAWL SDK instead of direct HTTP requests
            client = self._get_cawl_client()

            _logger.info("Fetching payment products using CAWL SDK")

            # Create the query parameters object - simplified approach
            from onlinepayments.sdk.merchant.products.get_payment_products_params import GetPaymentProductsParams

            query = GetPaymentProductsParams()
            query.country_code = 'FR'
            query.currency_code = 'EUR'
            query.amount = 1000
            query.hide = ['fields']

            # Get payment products using SDK with query object
            response = client.merchant(self.cawl_pspid).products().get_payment_products(query)

            # Extract products from response
            products = []
            for product in response.payment_products:
                # Extract product name from display hints
                product_name = f'Product {product.id}'
                if hasattr(product, 'display_hints') and product.display_hints and hasattr(product.display_hints, 'label'):
                    product_name = product.display_hints.label

                product_data = {
                    'id': product.id,
                    'name': product_name,
                    'payment_method': getattr(product, 'payment_method', 'unknown')
                }
                products.append(product_data)

            _logger.info("Successfully fetched %d payment products using CAWL SDK", len(products))
            return products

        except Exception as e:
            _logger.error("Error fetching payment products using SDK: %s", str(e))
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise UserError(_("Authentication failed. Please check your API credentials."))
            elif "forbidden" in str(e).lower():
                raise UserError(_("Access forbidden. Your API credentials don't have permission to fetch payment products."))
            elif "timeout" in str(e).lower():
                raise UserError(_("Request timeout. Please check your internet connection and try again."))
            else:
                raise UserError(_("Error fetching payment products: %s") % str(e))

    def _sync_payment_products(self, products_data):
        """ Sync payment products data to local model """
        self.ensure_one()

        # Get existing products for this provider
        existing_products = self.env['cawl.payment.product'].search([
            ('provider_id', '=', self.id)
        ])

        # Create/update products
        for product_data in products_data:
            try:
                # Handle different product data structures
                product_id = product_data.get('id') or product_data.get('productId')
                if not product_id:
                    _logger.warning("Skipping product without ID: %s", product_data)
                    continue

                # Extract name from different possible locations
                name = None
                if 'displayHints' in product_data and 'label' in product_data['displayHints']:
                    name = product_data['displayHints']['label']
                elif 'name' in product_data:
                    name = product_data['name']
                elif 'displayName' in product_data:
                    name = product_data['displayName']
                else:
                    name = f'Product {product_id}'

                # Extract payment method
                payment_method = product_data.get('paymentMethod') or product_data.get('method') or 'unknown'

                # Check if product already exists
                existing_product = existing_products.filtered(lambda p: p.product_id == product_id)

                if existing_product:
                    # Update existing product
                    existing_product.write({
                        'name': name,
                        'payment_method': payment_method,
                        'is_active': True
                    })
                    _logger.info("Updated product: %s (ID: %s)", name, product_id)
                else:
                    # Create new product
                    self.env['cawl.payment.product'].create({
                        'name': name,
                        'product_id': product_id,
                        'payment_method': payment_method,
                        'is_active': True,
                        'provider_id': self.id
                    })
                    _logger.info("Created product: %s (ID: %s)", name, product_id)

            except Exception as e:
                _logger.error("Error processing product data %s: %s", product_data, str(e))
                continue

        # Mark products not in API response as inactive
        api_product_ids = []
        for product_data in products_data:
            product_id = product_data.get('id') or product_data.get('productId')
            if product_id:
                api_product_ids.append(product_id)

        inactive_products = existing_products.filtered(lambda p: p.product_id not in api_product_ids)
        if inactive_products:
            inactive_products.write({'is_active': False})
            _logger.info("Marked %d products as inactive", len(inactive_products))

        _logger.info("Synced %d payment products for provider %s", len(products_data), self.name)
