import json
import logging
import pprint

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class CawlController(http.Controller):
    _return_url = "/payment/cawl/return"
    _webhook_url = "/payment/cawl/webhook"

    @http.route(
        "/payment/cawl/return/<int:tx_id>",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        save_session=False,
    )
    def cawl_return_from_checkout(self, tx_id, **data):
        """Handle the return from CAWL hosted checkout."""
        _logger.info(
            "Handling return from CAWL for transaction %s with data:\n%s",
            tx_id,
            pprint.pformat(data),
        )

        # Retrieve the transaction
        tx_sudo = request.env["payment.transaction"].sudo().browse(tx_id).exists()
        if not tx_sudo:
            _logger.warning("Could not find transaction with id %s", tx_id)
            raise ValidationError("Payment transaction not found.")

        # Handle the return data (following Stripe's pattern)
        try:
            self._handle_return_data(tx_sudo, data)
        except Exception as e:
            _logger.exception("Error processing CAWL return: %s", str(e))
            # DO NOT set error state here - let webhook handle it
            # This follows Stripe's pattern: return flow is passive

        # Redirect back to the confirmation page
        return self._redirect_to_portal(tx_sudo)

    @http.route(
        "/payment/cawl/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def cawl_webhook(self, **data):
        """Handle webhook notifications from CAWL."""
        _logger.info("=== CAWL WEBHOOK RECEIVED ===")
        _logger.info("Request Method: %s", request.httprequest.method)
        _logger.info("Request URL: %s", request.httprequest.url)
        _logger.info("Headers: %s", dict(request.httprequest.headers))
        _logger.info("Data: %s", pprint.pformat(data))
        _logger.info("Raw data: %s", request.httprequest.get_data())
        _logger.info(
            "Content-Type: %s",
            request.httprequest.headers.get("Content-Type", "Not set"),
        )
        _logger.info(
            "User-Agent: %s", request.httprequest.headers.get("User-Agent", "Not set")
        )

        try:
            # Get the raw request data for signature verification
            webhook_data = request.httprequest.get_data()
            webhook_signature = request.httprequest.headers.get("X-GCS-Signature", "")

            # Process the webhook
            self._handle_webhook_notification(webhook_data, webhook_signature, data)

            _logger.info("=== CAWL WEBHOOK PROCESSED SUCCESSFULLY ===")
            return "OK"  # Return success status to CAWL

        except Exception as e:
            _logger.exception("Error processing CAWL webhook: %s", str(e))
            return "ERROR"

    def _handle_return_data(self, tx_sudo, data):
        """Process the return data from CAWL hosted checkout."""
        _logger.info(
            "Processing return data for transaction %s: %s",
            tx_sudo.reference,
            pprint.pformat(data),
        )

        # Extract relevant data from CAWL return
        checkout_id = data.get("hostedCheckoutId")
        payment_id = data.get("paymentId")
        data.get("RETURNMAC")

        # Update transaction fields
        if checkout_id:
            tx_sudo.cawl_checkout_id = checkout_id
        if payment_id:
            tx_sudo.cawl_payment_id = payment_id

        # Validate the return data (basic validation)
        if not checkout_id:
            _logger.warning(
                "No checkout ID in return data for transaction %s", tx_sudo.reference
            )
            tx_sudo._set_error("Invalid return data from payment provider")
            return

        # For hosted checkout, we primarily rely on webhooks for status updates
        # The return URL is mainly for redirecting the user back to the merchant
        # DO NOT set transaction state here - let the webhook handle it
        # This follows Stripe's pattern: return flow just redirects, webhook handles state

        _logger.info(
            "Successfully processed return data for transaction %s - state unchanged, webhook will handle status",
            tx_sudo.reference,
        )

    def _handle_webhook_notification(self, webhook_data, signature, data):
        """Process webhook notification from CAWL."""
        # Decode webhook data if it's bytes
        if isinstance(webhook_data, bytes):
            webhook_data = webhook_data.decode("utf-8")

        try:
            # Parse JSON data from the raw webhook data
            if webhook_data:
                notification_data = json.loads(webhook_data)
            else:
                # Fallback to data parameter if webhook_data is empty
                if isinstance(data, str):
                    notification_data = json.loads(data)
                else:
                    notification_data = data

        except (json.JSONDecodeError, TypeError) as e:
            _logger.error(
                "Invalid JSON in CAWL webhook data: %s, Error: %s", webhook_data, str(e)
            )
            raise ValidationError("Invalid webhook data format")

        _logger.info(
            "Processing CAWL webhook notification: %s",
            pprint.pformat(notification_data),
        )

        # Find the transaction
        tx_sudo = self._get_tx_from_webhook_data(notification_data)
        if not tx_sudo:
            _logger.warning(
                "Could not find transaction for webhook data: %s",
                pprint.pformat(notification_data),
            )
            return

        # Verify webhook signature - webhook secret is MANDATORY for security
        if not tx_sudo.provider_id.cawl_webhook_secret:
            _logger.error(
                "Webhook secret not configured for provider %s - REJECTING webhook for security",
                tx_sudo.provider_id.name,
            )
            raise Forbidden(
                "Webhook secret not configured - webhook rejected for security"
            )

        if not signature:
            _logger.error(
                "No signature provided in webhook request - REJECTING webhook for security"
            )
            raise Forbidden(
                "No webhook signature provided - webhook rejected for security"
            )

        # Validate webhook signature
        if not self._verify_webhook_signature(
            tx_sudo.provider_id, webhook_data, signature
        ):
            _logger.error(
                "Invalid webhook signature for transaction %s - REJECTING webhook",
                tx_sudo.reference,
            )
            raise Forbidden("Invalid webhook signature - webhook rejected")

        # Process the notification
        tx_sudo._process_notification_data(notification_data)

    def _get_tx_from_webhook_data(self, notification_data):
        """Find the transaction from webhook notification data."""
        # Try to find by CAWL-specific identifiers
        checkout_id = notification_data.get("hostedCheckoutId")
        payment_id = notification_data.get("paymentId")
        merchant_ref = notification_data.get("merchantReference")

        # Handle CAWL's nested payment structure
        if "payment" in notification_data:
            payment_data = notification_data["payment"]
            if "paymentOutput" in payment_data:
                payment_output = payment_data["paymentOutput"]
                if "references" in payment_output:
                    merchant_ref = payment_output["references"].get("merchantReference")
                if "id" in payment_data:
                    payment_id = payment_data["id"]

        # Handle CAWL's refund structure
        if "refund" in notification_data:
            refund_data = notification_data["refund"]
            if "refundOutput" in refund_data:
                refund_output = refund_data["refundOutput"]
                if "references" in refund_output:
                    merchant_ref = refund_output["references"].get("merchantReference")

        tx_sudo = None

        # Try to find by checkout ID first
        if checkout_id:
            tx_sudo = (
                request.env["payment.transaction"]
                .sudo()
                .search([("cawl_checkout_id", "=", checkout_id)], limit=1)
            )

        # Try to find by payment ID
        if not tx_sudo and payment_id:
            tx_sudo = (
                request.env["payment.transaction"]
                .sudo()
                .search([("cawl_payment_id", "=", payment_id)], limit=1)
            )

        # Try to find by merchant reference (our transaction reference)
        if not tx_sudo and merchant_ref:
            tx_sudo = (
                request.env["payment.transaction"]
                .sudo()
                .search([("reference", "=", merchant_ref)], limit=1)
            )

        return tx_sudo

    def _verify_webhook_signature(self, provider, webhook_data, signature):
        """Verify the webhook signature using HMAC-SHA256 with base64 encoding."""
        try:
            import base64
            import hashlib
            import hmac

            # Calculate expected signature using HMAC-SHA256 with webhook secret
            hmac_obj = hmac.new(
                provider.cawl_webhook_secret.encode("utf-8"),  # webhook secret as key
                webhook_data.encode("utf-8")
                if isinstance(webhook_data, str)
                else webhook_data,
                hashlib.sha256,
            )

            # Get the digest and encode as base64
            expected_signature = base64.b64encode(hmac_obj.digest()).decode("utf-8")

            _logger.info(
                "Signature verification - Expected: %s, Received: %s",
                expected_signature,
                signature,
            )

            # Compare signatures (constant time comparison)
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            _logger.error("Error verifying webhook signature: %s", str(e))
            return False

    def _redirect_to_portal(self, tx_sudo):
        """Redirect the user back to the payment confirmation page.

        Following Stripe's pattern: always redirect to /payment/status
        and let Odoo's core payment system handle the display logic.
        """
        return request.redirect("/payment/status")

    @http.route(
        "/payment/cawl/simulate_return", type="http", auth="user", methods=["GET"]
    )
    def cawl_simulate_return(self, **data):
        """Simulate a return from CAWL (for testing purposes)."""
        if not request.env.user.has_group("base.group_system"):
            raise Forbidden()

        tx_id = data.get("tx_id")
        if not tx_id:
            return "Missing transaction ID"

        # Simulate return data
        test_data = {
            "hostedCheckoutId": f"test_checkout_{tx_id}",
            "paymentId": f"test_payment_{tx_id}",
            "RETURNMAC": "test_mac",
        }

        return self.cawl_return_from_checkout(int(tx_id), **test_data)

    @http.route(
        "/payment/cawl/simulate_webhook", type="http", auth="user", methods=["POST"]
    )
    def cawl_simulate_webhook(self, **data):
        """Simulate a webhook from CAWL (for testing purposes)."""
        if not request.env.user.has_group("base.group_system"):
            raise Forbidden()

        # Simulate webhook data
        test_data = {
            "hostedCheckoutId": data.get("checkout_id", "test_checkout_123"),
            "paymentId": data.get("payment_id", "test_payment_123"),
            "merchantReference": data.get("reference", "TEST-123"),
            "status": data.get("status", "PAID"),
            "amount": data.get("amount", 1000),
            "currency": data.get("currency", "EUR"),
        }

        try:
            self._handle_webhook_notification("", "", test_data)
            return "OK - Webhook simulated successfully"
        except Exception as e:
            return f"ERROR - {str(e)}"

    @http.route(
        "/payment/cawl/test_webhook", type="http", auth="public", methods=["GET"]
    )
    def cawl_test_webhook(self):
        """Test endpoint to verify webhook URL is accessible."""
        return "CAWL Webhook endpoint is accessible!"

    @http.route(
        "/payment/cawl/update_status/<int:tx_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def cawl_update_status(self, tx_id, status="PAID"):
        """Manually update transaction status (for testing)."""
        if not request.env.user.has_group("base.group_system"):
            raise Forbidden()

        tx_sudo = request.env["payment.transaction"].sudo().browse(tx_id).exists()
        if not tx_sudo:
            return "Transaction not found"

        # Simulate webhook data
        test_data = {
            "hostedCheckoutId": tx_sudo.cawl_checkout_id or "test_checkout",
            "paymentId": tx_sudo.cawl_payment_id or "test_payment",
            "merchantReference": tx_sudo.reference,
            "status": status,
            "amount": int(tx_sudo.amount * 100),  # Convert to cents
            "currency": tx_sudo.currency_id.name,
        }

        try:
            tx_sudo._process_notification_data(test_data)
            return f"Transaction {tx_sudo.reference} status updated to {status}"
        except Exception as e:
            return f"Error: {str(e)}"
