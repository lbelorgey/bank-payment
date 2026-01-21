#!/usr/bin/env python3
"""
CAWL SDK Test Script
===================

This script tests the CAWL SDK outside of Odoo to debug the
"NoneType object cannot be interpreted as an integer" error.

Usage:
1. Copy config.example.py to config.py
2. Fill in your CAWL credentials in config.py
3. Run: python3 test_cawl_sdk.py
"""

import sys
import traceback

try:
    import config
except ImportError:
    print("❌ Error: config.py not found!")
    print("Please copy config.example.py to config.py and fill in your credentials")
    sys.exit(1)


def test_simple_api_call():
    """Test simple API calls first"""
    print("🔧 Testing simple API calls...")

    try:
        from onlinepayments.sdk.communicator_configuration import (
            CommunicatorConfiguration,
        )
        from onlinepayments.sdk.factory import Factory

        print("✅ SDK imports successful")

        # Debug: Check CommunicatorConfiguration constructor
        from inspect import signature

        print("🔍 CommunicatorConfiguration signature:")
        sig = signature(CommunicatorConfiguration.__init__)
        print(f"   Parameters: {list(sig.parameters.keys())}")

        # Create configuration with max_connections to fix pool issue
        sdk_config = CommunicatorConfiguration(
            api_endpoint=config.API_ENDPOINT,
            api_key_id=str(config.API_KEY),
            secret_api_key=str(config.API_SECRET),
            authorization_type="v1HMAC",
            integrator="CAWL-Test-Script",
            connect_timeout=10,
            socket_timeout=15,
            max_connections=10,  # Fix for 'NoneType' object cannot be interpreted as an integer
        )

        print("✅ Configuration created")
        print(f"   Endpoint: {config.API_ENDPOINT}")
        print(f"   API Key: {config.API_KEY[:8]}...")
        print(f"   Merchant ID: {config.MERCHANT_ID}")

        # Create client
        client = Factory.create_client_from_configuration(sdk_config)
        print("✅ Client created")

        # Test merchant client
        merchant_client = client.merchant(config.MERCHANT_ID)
        print("✅ Merchant client created")

        # Debug: Check what methods are available on merchant_client
        print("🔍 Checking available methods on merchant_client...")
        available_methods = [
            method for method in dir(merchant_client) if not method.startswith("_")
        ]
        print(f"   Available methods: {available_methods}")

        # Test hosted_checkout method (which we know exists)
        try:
            print("🔍 Testing hosted_checkout client creation...")
            hosted_checkout_client = merchant_client.hosted_checkout()
            print("✅ Hosted checkout client created successfully!")
            print(f"   Client type: {type(hosted_checkout_client)}")

            # Debug: Check methods on hosted_checkout_client
            hc_methods = [
                method
                for method in dir(hosted_checkout_client)
                if not method.startswith("_")
            ]
            print(f"   Available HC methods: {hc_methods}")

            return True
        except Exception as e:
            print(f"❌ Hosted checkout client failed: {e}")
            return False

    except Exception as e:
        print(f"❌ Simple API test failed: {e}")
        traceback.print_exc()
        return False


def test_hosted_checkout_minimal():
    """Test minimal hosted checkout creation"""
    print("\n🏪 Testing minimal hosted checkout creation...")

    try:
        from onlinepayments.sdk.communicator_configuration import (
            CommunicatorConfiguration,
        )
        from onlinepayments.sdk.domain.amount_of_money import AmountOfMoney
        from onlinepayments.sdk.domain.create_hosted_checkout_request import (
            CreateHostedCheckoutRequest,
        )
        from onlinepayments.sdk.domain.hosted_checkout_specific_input import (
            HostedCheckoutSpecificInput,
        )
        from onlinepayments.sdk.domain.order import Order
        from onlinepayments.sdk.factory import Factory

        print("✅ Domain imports successful")

        # Debug: Check CommunicatorConfiguration constructor
        from inspect import signature

        print("🔍 CommunicatorConfiguration signature:")
        sig = signature(CommunicatorConfiguration.__init__)
        print(f"   Parameters: {list(sig.parameters.keys())}")

        # Create configuration with max_connections to fix pool issue
        sdk_config = CommunicatorConfiguration(
            api_endpoint=config.API_ENDPOINT,
            api_key_id=str(config.API_KEY),
            secret_api_key=str(config.API_SECRET),
            authorization_type="v1HMAC",
            integrator="CAWL-Test-Script",
            connect_timeout=10,
            socket_timeout=15,
            max_connections=10,  # Fix for 'NoneType' object cannot be interpreted as an integer
        )

        client = Factory.create_client_from_configuration(sdk_config)
        merchant_client = client.merchant(config.MERCHANT_ID)
        hosted_checkout_client = merchant_client.hosted_checkout()

        print("✅ Clients created")

        # Create minimal request
        request = CreateHostedCheckoutRequest()

        # Hosted checkout input
        hosted_input = HostedCheckoutSpecificInput()
        hosted_input.locale = "en_US"
        hosted_input.return_url = "https://test.local/return"
        request.hosted_checkout_specific_input = hosted_input

        print("✅ Hosted checkout input created")
        print(f"   Locale: {hosted_input.locale}")
        print(f"   Return URL: {hosted_input.return_url}")

        # Order with amount
        order = Order()
        amount = AmountOfMoney()
        amount.amount = 100  # 1.00 EUR in cents
        amount.currency_code = "EUR"
        order.amount_of_money = amount
        request.order = order

        print("✅ Order created")
        print(f"   Amount: {amount.amount}")
        print(f"   Currency: {amount.currency_code}")
        print(f"   Amount type: {type(amount.amount)}")

        # Debug the request object
        print("\n🔍 Request object details:")
        print(f"   Request type: {type(request)}")
        print(f"   Has order: {hasattr(request, 'order')}")
        print(
            f"   Has hosted_checkout_specific_input: {hasattr(request, 'hosted_checkout_specific_input')}"
        )

        if hasattr(request.order, "amount_of_money"):
            print(f"   Order.amount_of_money: {request.order.amount_of_money}")
            if request.order.amount_of_money:
                print(f"   Amount value: {request.order.amount_of_money.amount}")
                print(f"   Amount type: {type(request.order.amount_of_money.amount)}")
                print(f"   Currency: {request.order.amount_of_money.currency_code}")

        # Try the API call
        print("\n🚀 Making hosted checkout API call...")
        try:
            response = hosted_checkout_client.create_hosted_checkout(request)
            print("✅ Hosted checkout creation successful!")
            print(f"   Response type: {type(response)}")
            if hasattr(response, "hosted_checkout_id"):
                print(f"   Checkout ID: {response.hosted_checkout_id}")
            if hasattr(response, "partial_redirect_url"):
                print(f"   Redirect URL: {response.partial_redirect_url}")
            return True
        except Exception as api_error:
            print(f"❌ Hosted checkout API call failed: {api_error}")
            print(f"   Error type: {type(api_error)}")
            traceback.print_exc()
            return False

    except Exception as e:
        print(f"❌ Hosted checkout test failed: {e}")
        traceback.print_exc()
        return False


def test_hosted_checkout_with_customer():
    """Test hosted checkout with customer data"""
    print("\n👤 Testing hosted checkout with customer data...")

    try:
        from onlinepayments.sdk.communicator_configuration import (
            CommunicatorConfiguration,
        )
        from onlinepayments.sdk.domain.amount_of_money import AmountOfMoney
        from onlinepayments.sdk.domain.create_hosted_checkout_request import (
            CreateHostedCheckoutRequest,
        )
        from onlinepayments.sdk.domain.customer import Customer
        from onlinepayments.sdk.domain.hosted_checkout_specific_input import (
            HostedCheckoutSpecificInput,
        )
        from onlinepayments.sdk.domain.order import Order
        from onlinepayments.sdk.domain.personal_name import PersonalName
        from onlinepayments.sdk.factory import Factory

        # Create configuration and clients
        sdk_config = CommunicatorConfiguration(
            api_endpoint=config.API_ENDPOINT,
            api_key_id=str(config.API_KEY),
            secret_api_key=str(config.API_SECRET),
            authorization_type="v1HMAC",
            integrator="CAWL-Test-Script",
            connect_timeout=10,
            socket_timeout=15,
            max_connections=10,
        )

        client = Factory.create_client_from_configuration(sdk_config)
        merchant_client = client.merchant(config.MERCHANT_ID)
        hosted_checkout_client = merchant_client.hosted_checkout()

        # Create comprehensive request
        request = CreateHostedCheckoutRequest()

        # Hosted checkout input
        hosted_input = HostedCheckoutSpecificInput()
        hosted_input.locale = "en_US"
        hosted_input.return_url = "https://test.local/return"
        request.hosted_checkout_specific_input = hosted_input

        # Order with amount and customer
        order = Order()

        # Amount
        amount = AmountOfMoney()
        amount.amount = 100
        amount.currency_code = "EUR"
        order.amount_of_money = amount

        # Customer
        customer = Customer()
        customer.merchant_customer_id = "test_customer_123"

        # Personal name
        personal_name = PersonalName()
        personal_name.first_name = "Test"
        personal_name.surname = "Customer"
        customer.personal_information = personal_name

        order.customer = customer
        request.order = order

        print("✅ Comprehensive request created")
        print(f"   Customer ID: {customer.merchant_customer_id}")
        print(f"   Customer name: {personal_name.first_name} {personal_name.surname}")

        # Try the API call
        print("\n🚀 Making comprehensive hosted checkout API call...")
        try:
            hosted_checkout_client.create_hosted_checkout(request)
            print("✅ Comprehensive hosted checkout creation successful!")
            return True
        except Exception as api_error:
            print(f"❌ Comprehensive hosted checkout API call failed: {api_error}")
            traceback.print_exc()
            return False

    except Exception as e:
        print(f"❌ Comprehensive hosted checkout test failed: {e}")
        traceback.print_exc()
        return False


def test_hosted_checkout_minimal_without_sdk():
    """Test minimal hosted checkout creation without SDK"""
    print("\n🏪 Testing minimal hosted checkout creation without SDK...")

    try:
        import base64
        import datetime
        import hashlib
        import hmac

        import requests

        merchant_id = config.MERCHANT_ID
        api_key = config.API_KEY
        api_secret = config.API_SECRET

        # Get current time
        tz = datetime.timezone(datetime.timedelta(hours=0), "GMT")
        dt = datetime.datetime.now(tz)
        date_time = dt.strftime("%a, %d %b %Y %H:%M:%S %Z")
        print("\nCurrent time: " + date_time)

        # Create string to hash
        endpoint_uri = "/v2/" + merchant_id + "/hostedcheckouts"
        content_type = "application/json"
        string_to_hash = (
            "POST" + "\n" + content_type + "\n" + date_time + "\n" + endpoint_uri + "\n"
        )
        print("\nString to hash: " + string_to_hash)

        h = hmac.new(
            api_secret.encode("utf-8"), string_to_hash.encode("utf-8"), hashlib.sha256
        )
        hash = base64.b64encode(h.digest()).decode("utf-8")
        print("\nHash: " + hash)

        # Make the API call
        print("\n🚀 Making minimal hosted checkout API call without SDK...")
        try:
            url = "https://payment.preprod.cawl-solutions.fr" + endpoint_uri
            authorization_header_value = "GCS v1HMAC:" + api_key + ":" + hash
            headers = {
                "Authorization": authorization_header_value,
                "Date": date_time,
                "Content-Type": content_type,
            }

            # Create minimal request
            request_body = {
                "hostedCheckoutSpecificInput": {
                    "locale": "en_US",
                    "returnUrl": "https://test.local/return",
                },
                "order": {"amountOfMoney": {"currencyCode": "EUR", "amount": 100}},
            }
            response = requests.post(url, headers=headers, json=request_body)
            response.raise_for_status()
            print("✅ Minimal hosted checkout API call successful!")
            print(f"   Response: {response.json()}")
            return True
        except Exception as e:
            print(f"❌ Minimal hosted checkout API call failed: {e}")

            # Log detailed error response for HTTP errors
            if hasattr(e, "response") and e.response is not None:
                print(f"   HTTP Status: {e.response.status_code}")
                try:
                    error_detail = e.response.json()
                    print(f"   Error Response: {error_detail}")
                except:
                    print(f"   Error Response (raw): {e.response.text}")
            elif "400" in str(e) or "Bad Request" in str(e):
                print("   HTTP 400 Bad Request - check request format")

            traceback.print_exc()
            return False

    except Exception as e:
        print(f"❌ Minimal hosted checkout test failed: {e}")
        traceback.print_exc()
        return False


def main():
    print("🧪 CAWL SDK Test Script")
    print("=" * 50)

    # Run tests in order
    tests = [
        ("Simple API Call", test_simple_api_call),
        ("Minimal Hosted Checkout", test_hosted_checkout_minimal),
        ("Hosted Checkout with Customer", test_hosted_checkout_with_customer),
        (
            "Minimal Hosted Checkout without SDK",
            test_hosted_checkout_minimal_without_sdk,
        ),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 30)
        success = test_func()
        results.append((test_name, success))

        if not success:
            print(f"\n⚠️  {test_name} failed - stopping here for debugging")
            break

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} {test_name}")

    if all(success for _, success in results):
        print("\n🎉 All tests passed! The SDK is working correctly.")
    else:
        print("\n🔍 Some tests failed. Check the error messages above for debugging.")


if __name__ == "__main__":
    main()
