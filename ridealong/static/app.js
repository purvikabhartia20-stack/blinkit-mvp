const FREE_DELIVERY_MINIMUM = 200;

const state = {
  users: [],
  products: [],
  userId: 1,
  cart: new Map(),
  category: "all",
  searchQuery: "",
  evaluation: null,
  trialProduct: null,
  submitting: false,
};

const presets = {
  gap: [1, 2, 3, 8, 9], // ₹157, five familiar items
  stocking: [4, 5, 11, 12], // ₹297, four familiar items
  exploring: [1, 2, 3, 14], // Beauty is new to User A
  none: [1, 2], // Small routine basket
};

const reasonCopy = {
  gap_fill_eligible: "The cart is close enough to free delivery for Gap-Fill.",
  stocking_up_eligible: "The cart has at least four items, indicating a stocking-up mission.",
  already_exploring: "A new-to-this-user category is already in the cart, so RideAlong steps aside.",
  not_frequent_user: "RideAlong is restricted to frequent shoppers.",
  weekly_fire_cap: "This user has already seen an offer in the last seven days.",
  single_item_cart: "Single-item task-completion orders are never interrupted.",
  suppressed_category: "The cart contains a sensitive or urgent category.",
  no_trigger_matched: "The cart matched neither Gap-Fill nor Stocking-Up.",
  no_eligible_product: "The moment qualified, but no product passed every safety and relevance filter.",
};

const elements = {
  userSelect: document.querySelector("#user-select"),
  userMeta: document.querySelector("#user-meta"),
  resetDemo: document.querySelector("#reset-demo"),
  categoryStrip: document.querySelector("#category-strip"),
  catalogGrid: document.querySelector("#catalog-grid"),
  catalogCount: document.querySelector("#catalog-count"),
  showAll: document.querySelector("#show-all"),
  searchInput: document.querySelector("#search-input"),
  cartDock: document.querySelector("#cart-dock"),
  cartSummary: document.querySelector("#cart-summary"),
  cartTotalTop: document.querySelector("#cart-total-top"),
  deliveryLabel: document.querySelector("#delivery-label"),
  progressFill: document.querySelector("#progress-fill"),
  checkout: document.querySelector("#checkout-button"),
  trialSheet: document.querySelector("#trial-sheet"),
  trialPath: document.querySelector("#trial-path"),
  trialSwatch: document.querySelector("#trial-swatch"),
  trialCategoryLabel: document.querySelector("#trial-category"),
  trialTitle: document.querySelector("#trial-name"),
  trialName: document.querySelector("#trial-name"),
  trialPrice: document.querySelector("#trial-price"),
  trialMessage: document.querySelector("#trial-message"),
  acceptTrial: document.querySelector("#accept-trial"),
  declineTrial: document.querySelector("#decline-trial"),
  confirmation: document.querySelector("#confirmation-screen"),
  confirmationCopy: document.querySelector("#confirmation-copy"),
  finalOrder: document.querySelector("#final-order"),
  newOrder: document.querySelector("#new-order"),
  mechanismEmpty: document.querySelector("#mechanism-empty"),
  mechanismOutput: document.querySelector("#mechanism-output"),
  decisionBadge: document.querySelector("#decision-badge"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionReason: document.querySelector("#decision-reason"),
  mechanismData: document.querySelector("#mechanism-data"),
  rawResponse: document.querySelector("#raw-response"),
  toast: document.querySelector("#toast"),
};

function money(value) {
  return `₹${Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}

function titleCase(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({
    error: "The server returned an unreadable response.",
  }));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 2800);
}

function productById(productId) {
  return state.products.find((product) => product.product_id === productId);
}

function cartEntries() {
  return [...state.cart.entries()]
    .map(([productId, quantity]) => ({
      product: productById(productId),
      quantity,
    }))
    .filter((entry) => entry.product && entry.quantity > 0);
}

function cartMetrics() {
  const entries = cartEntries();
  return {
    count: entries.reduce((sum, entry) => sum + entry.quantity, 0),
    total: entries.reduce(
      (sum, entry) => sum + entry.product.price * entry.quantity,
      0,
    ),
    categories: [...new Set(entries.map((entry) => entry.product.category))],
  };
}

function setQuantity(productId, quantity) {
  if (quantity <= 0) {
    state.cart.delete(productId);
  } else {
    state.cart.set(productId, quantity);
  }
  renderCatalog();
  renderCart();
}

function renderUsers() {
  elements.userSelect.innerHTML = state.users
    .map(
      (user) =>
        `<option value="${user.user_id}">${escapeHTML(user.name)}</option>`,
    )
    .join("");
  elements.userSelect.value = String(state.userId);
}

async function renderUserMeta() {
  elements.userMeta.textContent = "Loading shopper history…";
  try {
    const history = await api(`/api/user/${state.userId}/history`);
    const average =
      history.personal_average_order_value == null
        ? "No personal average yet"
        : `${money(history.personal_average_order_value)} average`;
    elements.userMeta.textContent = `${history.order_count} past orders · ${average}`;
  } catch (error) {
    elements.userMeta.textContent = error.message;
  }
}

function categoryColor(category) {
  return (
    state.products.find((product) => product.category === category)?.color_hex ||
    "#F5F5F5"
  );
}

// Emoji icons for known categories — falls back to first-letter initial
const CATEGORY_EMOJI = {
  all: "🏪",
  grocery: "🥦",
  snacks: "🍟",
  beverages: "🥤",
  personal_care: "🧴",
  beauty: "💄",
  home_fragrance: "🕯️",
  stationery: "📎",
  household: "🧹",
  electronics_accessories: "🔌",
  pharmacy: "💊",
  baby_care: "👶",
  baby_toys: "🧸",
};

function renderCategories() {
  const categories = [
    "all",
    ...new Set(state.products.map((product) => product.category)),
  ];
  elements.categoryStrip.innerHTML = categories
    .map((category) => {
      const label = category === "all" ? "All" : titleCase(category);
      const color = category === "all" ? "#F8CB46" : categoryColor(category);
      const emoji = CATEGORY_EMOJI[category] || category.charAt(0).toUpperCase();
      const isActive = state.category === category;
      return `
        <button class="cat-chip ${isActive ? "active" : ""}"
                type="button" data-category="${escapeHTML(category)}">
          <div class="cat-tile" style="background:${color}33">
            ${emoji}
          </div>
          <span class="cat-label">${escapeHTML(label)}</span>
        </button>
      `;
    })
    .join("");
}

function productCard(product) {
  const quantity = state.cart.get(product.product_id) || 0;
  const control = !product.in_stock
    ? `<button class="btn-add" type="button" disabled>Out of stock</button>`
    : quantity > 0
      ? `<div class="qty-stepper" aria-label="${escapeHTML(product.name)} quantity">
          <button type="button" data-action="decrease"
                  data-product-id="${product.product_id}"
                  aria-label="Remove one ${escapeHTML(product.name)}">−</button>
          <span>${quantity}</span>
          <button type="button" data-action="increase"
                  data-product-id="${product.product_id}"
                  aria-label="Add one ${escapeHTML(product.name)}">+</button>
        </div>`
      : `<button class="btn-add" type="button"
                 data-action="increase"
                 data-product-id="${product.product_id}">ADD</button>`;

  return `
    <article class="product-card ${product.in_stock ? "" : "oos"}">
      <div class="prod-img" style="background:${product.color_hex}1A" aria-hidden="true">
        ${!product.in_stock ? `<span class="oos-tag">Out of stock</span>` : ""}
        <span class="prod-swatch" style="background:${product.color_hex}"></span>
      </div>
      <p class="prod-cat">${escapeHTML(titleCase(product.category))}</p>
      <h3 class="prod-name">${escapeHTML(product.name)}</h3>
      <div class="prod-bottom">
        <span class="prod-price">${money(product.price)}</span>
        ${control}
      </div>
    </article>
  `;
}

function renderCatalog() {
  let products =
    state.category === "all"
      ? state.products
      : state.products.filter(
          (product) => product.category === state.category,
        );
  const q = (state.searchQuery || "").toLowerCase();
  if (q) {
    products = products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q),
    );
  }
  elements.catalogCount.textContent = `${products.length} product${products.length !== 1 ? "s" : ""}`;
  elements.catalogGrid.innerHTML = products.length
    ? products.map(productCard).join("")
    : `<p class="empty-state">No products match "${escapeHTML(q)}"</p>`;
}

function renderCart() {
  const { count, total } = cartMetrics();
  elements.cartDock.hidden = count === 0;
  elements.checkout.disabled = count === 0 || state.submitting;
  elements.cartSummary.textContent = `${count} ${count === 1 ? "item" : "items"} · ${money(total)}`;
  elements.cartTotalTop.textContent = money(total);

  const amountAway = Math.max(0, FREE_DELIVERY_MINIMUM - total);
  elements.deliveryLabel.textContent =
    amountAway > 0
      ? `₹${Math.ceil(amountAway)} away from free delivery`
      : "🎉 Free delivery unlocked!";
  elements.progressFill.style.width = `${Math.min(100, (total / FREE_DELIVERY_MINIMUM) * 100)}%`;
}

function resetExperience({ clearMechanism = true } = {}) {
  state.cart.clear();
  state.evaluation = null;
  state.trialProduct = null;
  state.submitting = false;
  state.searchQuery = "";
  if (elements.searchInput) elements.searchInput.value = "";
  elements.trialSheet.hidden = true;
  elements.confirmation.hidden = true;
  elements.cartDock.hidden = true;
  document.querySelector(".phone-body").hidden = false;
  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.classList.remove("active");
  });
  if (clearMechanism) {
    elements.mechanismEmpty.hidden = false;
    elements.mechanismOutput.hidden = true;
  }
  renderCatalog();
  renderCart();
}

function loadPreset(name) {
  state.cart.clear();
  for (const productId of presets[name]) {
    state.cart.set(productId, 1);
  }
  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.classList.toggle("active", button.dataset.preset === name);
  });
  renderCatalog();
  renderCart();
  showToast(`${titleCase(name)} cart loaded for User A`);
}

function mechanismRows(response) {
  const detail = response.detail || {};
  const rows = [
    ["Path", response.path ? titleCase(response.path) : "None"],
    ["Reason", titleCase(detail.reason || "unknown")],
  ];
  if (detail.cart_value != null) rows.push(["Cart value", money(detail.cart_value)]);
  if (detail.item_count != null) rows.push(["Item count", detail.item_count]);
  if (detail.gap != null) rows.push(["Free-delivery gap", money(detail.gap)]);
  if (detail.orders_last_7_days != null) {
    rows.push(["Orders in 7 days", detail.orders_last_7_days]);
  }
  if (detail.orders_last_28_days != null) {
    rows.push(["Orders in 28 days", detail.orders_last_28_days]);
  }
  if (detail.new_categories_in_cart) {
    rows.push(["New category in cart", detail.new_categories_in_cart.join(", ")]);
  }
  if (response.product) {
    rows.push(["Chosen product", response.product.name]);
    rows.push(["New category", titleCase(response.product.category)]);
    rows.push(["Affinity score", response.affinity_score]);
    rows.push([
      "Selection mode",
      titleCase(response.product.selection_mode || "affinity ranking"),
    ]);
    if (response.product.trial_value_cap != null) {
      rows.push(["Trial value cap", money(response.product.trial_value_cap)]);
    }
  }
  if (response.message_source) {
    rows.push(["Message source", response.message_source]);
  }
  return rows;
}

function renderMechanism(response) {
  elements.mechanismEmpty.hidden = true;
  elements.mechanismOutput.hidden = false;
  elements.decisionBadge.textContent = response.triggered ? "TRIGGERED" : "NO OFFER";
  elements.decisionBadge.classList.toggle("no", !response.triggered);
  elements.decisionTitle.textContent = response.triggered
    ? titleCase(response.path)
    : "RideAlong stayed quiet";
  elements.decisionReason.textContent =
    reasonCopy[response.detail?.reason] || response.detail?.reason || "";
  elements.mechanismData.innerHTML = mechanismRows(response)
    .map(
      ([label, value]) =>
        `<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value)}</dd></div>`,
    )
    .join("");
  elements.rawResponse.textContent = JSON.stringify(response, null, 2);
}

function showTrial(response) {
  const product = response.product;
  state.trialProduct = product;
  elements.trialPath.textContent = titleCase(response.path);
  elements.trialSwatch.style.background = product.color_hex;
  if (elements.trialCategoryLabel) {
    elements.trialCategoryLabel.textContent = titleCase(product.category);
  }
  if (elements.trialTitle) elements.trialTitle.textContent = product.name;
  elements.trialPrice.textContent = money(product.price);
  elements.trialMessage.textContent = response.message;
  elements.trialSheet.hidden = false;
  elements.acceptTrial.disabled = false;
  elements.declineTrial.disabled = false;
  elements.acceptTrial.focus();
}

function renderConfirmation(keptTrial) {
  const entries = cartEntries();
  const trial = keptTrial ? state.trialProduct : null;
  const total =
    entries.reduce(
      (sum, entry) => sum + entry.product.price * entry.quantity,
      0,
    ) + (trial ? trial.price : 0);

  elements.confirmationCopy.textContent = trial
    ? `Your order includes ${trial.name}, a first purchase from ${titleCase(trial.category)}.`
    : "Your basket is confirmed exactly as selected.";
  elements.finalOrder.innerHTML = [
    ...entries.map(
      ({ product, quantity }) => `
        <div class="final-row">
          <span>${quantity} × ${escapeHTML(product.name)}</span>
          <strong>${money(product.price * quantity)}</strong>
        </div>`,
    ),
    ...(trial
      ? [
          `<div class="final-row trial-row">
            <span>TRIAL · ${escapeHTML(trial.name)}</span>
            <strong>${money(trial.price)}</strong>
          </div>`,
        ]
      : []),
    `<div class="final-row">
      <strong>Total</strong>
      <strong>${money(total)}</strong>
    </div>`,
  ].join("");
  elements.trialSheet.hidden = true;
  document.querySelector(".phone-body").hidden = true;
  elements.cartDock.hidden = true;
  elements.confirmation.hidden = false;
  elements.newOrder.focus();
}

async function checkout() {
  if (state.submitting) return;
  const metrics = cartMetrics();
  if (metrics.count === 0) return;

  state.submitting = true;
  elements.checkout.disabled = true;
  const checkoutItems = elements.checkout.querySelector(".checkout-items");
  const prevText = checkoutItems ? checkoutItems.textContent : "";
  if (checkoutItems) checkoutItems.textContent = "Checking…";
  try {
    const response = await api("/api/evaluate", {
      method: "POST",
      body: JSON.stringify({
        user_id: state.userId,
        cart_value: metrics.total,
        item_count: metrics.count,
        cart_categories: metrics.categories,
      }),
    });
    state.evaluation = response;
    renderMechanism(response);
    if (response.triggered) {
      showTrial(response);
    } else {
      renderConfirmation(false);
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    state.submitting = false;
    if (checkoutItems) checkoutItems.textContent = prevText;
    renderCart();
  }
}

async function resolveTrial(keptTrial) {
  if (state.submitting || !state.trialProduct) return;
  state.submitting = true;
  elements.acceptTrial.disabled = true;
  elements.declineTrial.disabled = true;
  try {
    if (!keptTrial) {
      await api("/api/decline", {
        method: "POST",
        body: JSON.stringify({
          user_id: state.userId,
          product_id: state.trialProduct.product_id,
        }),
      });
    }
    await api("/api/confirm", {
      method: "POST",
      body: JSON.stringify({
        user_id: state.userId,
        kept_trial: keptTrial,
        ...(keptTrial
          ? { product_id: state.trialProduct.product_id }
          : {}),
      }),
    });
    renderConfirmation(keptTrial);
  } catch (error) {
    showToast(error.message);
    elements.acceptTrial.disabled = false;
    elements.declineTrial.disabled = false;
  } finally {
    state.submitting = false;
  }
}

async function initialize() {
  try {
    const [usersResponse, catalogResponse] = await Promise.all([
      api("/api/users"),
      api("/api/catalog"),
    ]);
    state.users = usersResponse.users;
    state.products = catalogResponse.products;
    state.userId = state.users[0]?.user_id || 1;
    renderUsers();
    renderCategories();
    renderCatalog();
    renderCart();
    await renderUserMeta();
  } catch (error) {
    elements.catalogGrid.innerHTML = `<p class="empty-state">${escapeHTML(error.message)}</p>`;
    showToast(error.message);
  }
}

elements.userSelect.addEventListener("change", async (event) => {
  state.userId = Number(event.target.value);
  resetExperience();
  await renderUserMeta();
  showToast("Shopper changed — cart cleared");
});

elements.resetDemo.addEventListener("click", async () => {
  if (state.submitting) return;
  state.submitting = true;
  elements.resetDemo.disabled = true;
  try {
    await api("/api/demo/reset", {
      method: "POST",
      body: JSON.stringify({}),
    });
    resetExperience();
    showToast("Demo reset — weekly cap and declines cleared");
  } catch (error) {
    showToast(error.message);
  } finally {
    state.submitting = false;
    elements.resetDemo.disabled = false;
  }
});

elements.categoryStrip.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  state.category = button.dataset.category;
  renderCategories();
  renderCatalog();
});

elements.showAll.addEventListener("click", () => {
  state.category = "all";
  renderCategories();
  renderCatalog();
});

elements.catalogGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const productId = Number(button.dataset.productId);
  const current = state.cart.get(productId) || 0;
  setQuantity(
    productId,
    button.dataset.action === "increase" ? current + 1 : current - 1,
  );
});

document.querySelector(".preset-row").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-preset]");
  if (!button) return;
  if (state.userId !== 1) {
    state.userId = 1;
    elements.userSelect.value = "1";
    await renderUserMeta();
  }
  elements.confirmation.hidden = true;
  document.querySelector(".phone-body").hidden = false;
  loadPreset(button.dataset.preset);
});

elements.checkout.addEventListener("click", checkout);
elements.acceptTrial.addEventListener("click", () => resolveTrial(true));
elements.declineTrial.addEventListener("click", () => resolveTrial(false));
elements.newOrder.addEventListener("click", () => resetExperience());

// Search filtering
if (elements.searchInput) {
  elements.searchInput.addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    state.searchQuery = q;
    renderCatalog();
  });
}

// Tap backdrop to dismiss trial sheet
document.querySelector("#trial-backdrop")?.addEventListener("click", () => {
  elements.trialSheet.hidden = true;
});

initialize();
