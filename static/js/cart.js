document.addEventListener("DOMContentLoaded", function () {
  console.log("cart.js loaded ✅");

  const placeOrderBtn = document.getElementById("placeOrderBtn");

  if (!placeOrderBtn) {
    console.error("❌ Place Order button NOT found");
    return;
  }

  placeOrderBtn.addEventListener("click", function () {
    console.log("🟢 Place Order clicked");
    placeOrder();
  });
});

function placeOrder() {
  console.log("🚀 placeOrder() called");

  const cart = JSON.parse(localStorage.getItem("cart")) || [];

  if (cart.length === 0) {
    alert("Cart is empty");
    return;
  }

  fetch("/place_order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      items: cart   // ✅ ONLY SEND ITEMS
    })
  })
    .then(res => res.json())
    .then(data => {
      alert("Order placed successfully✅");
      localStorage.removeItem("cart");
      window.location.href = "/menu";   // ✅ no table in URL
    })
    .catch(err => {
      console.error("❌ Error:", err);
    });
}

