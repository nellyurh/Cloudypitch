import React, { useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import api from "../lib/api";

export const PaymentCallback = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const reference = params.get("reference") || params.get("trxref");
  useEffect(() => {
    (async () => {
      if (!reference) { navigate("/wallet"); return; }
      try {
        const { data } = await api.get(`/payments/paystack/verify/${reference}`);
        if (data.status === "success") {
          navigate("/wallet?ok=1");
        } else {
          navigate("/wallet?failed=1");
        }
      } catch (_) {
        navigate("/wallet?failed=1");
      }
    })();
  }, [reference, navigate]);
  return (
    <div className="cp-surface p-10 text-center" data-testid="payment-callback">
      <div className="text-xl font-extrabold">Verifying payment…</div>
      <div className="text-sm mt-2" style={{ color: "var(--cp-text-muted)" }}>Hang tight — this only takes a second.</div>
    </div>
  );
};

export default PaymentCallback;
