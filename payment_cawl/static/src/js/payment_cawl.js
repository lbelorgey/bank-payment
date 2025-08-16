odoo.define('payment_cawl.payment_form', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    /**
     * CAWL Payment Widget
     * Simple widget to handle auto-redirect to CAWL hosted checkout
     */
    var CawlPaymentWidget = publicWidget.Widget.extend({
        template: 'payment_cawl_redirect_form',
        
        /**
         * Start the widget and auto-redirect
         */
        start: function () {
            var self = this;
            
            // Auto-redirect after a short delay to show loading state
            setTimeout(function () {
                var form = self.$('form');
                if (form.length) {
                    form.submit();
                }
            }, 1500);
            
            return this._super.apply(this, arguments);
        },
    });

    // Register the widget
    publicWidget.registry.CawlPaymentWidget = CawlPaymentWidget;

    return CawlPaymentWidget;
});