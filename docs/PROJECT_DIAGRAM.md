# Project diagrams — E-Commerce API

Visual overview of the **api-comerce-in** backend (onion architecture). Diagrams use [Mermaid](https://mermaid.js.org/); they render in GitHub, GitLab, many IDEs, and some Markdown viewers.

---

## 1. Onion layers (dependency direction)

Outer layers depend inward; **domain** has no framework imports.

```mermaid
flowchart TB
  subgraph api_layer [api]
    main[main.py]
    routers[routers: auth, products, cart, admin]
    schemas[schemas + deps]
    main --> routers
    routers --> schemas
  end

  subgraph app_layer [application]
    auth_svc[auth_service]
    prod_svc[product_service]
    cart_svc[cart_service]
  end

  subgraph dom_layer [domain]
    rules[ecommerce_rules]
  end

  subgraph infra_layer [infrastructure]
    settings[config/settings]
    db[(SQLAlchemy models + session)]
    sec[security: jwt, password]
  end

  api_layer --> app_layer
  app_layer --> dom_layer
  app_layer --> infra_layer
  dom_layer -.->|no imports from outer| infra_layer
```

---

## 2. Request path (typical HTTP call)

```mermaid
sequenceDiagram
  participant C as Client
  participant R as Router
  participant D as Deps / DbSession
  participant S as Application service
  participant DOM as Domain rules
  participant DB as DB models / Session

  C->>R: HTTP request
  R->>D: Depends: DB, settings, CurrentUser
  D->>DB: Session
  R->>S: use-case function
  S->>DOM: validate business rules
  S->>DB: read / write
  DB-->>S: rows
  S-->>R: entities / result
  R-->>C: JSON response
```

---https://youtu.be/vPzBiQc44i4?si=mVBmh1lJRcYpVyIo

## 3. API surface (`/api/v1`)

```mermaid
flowchart LR
  subgraph v1 [/api/v1]
    auth[/auth — signup, login, me/]
    products[/products — list, get/]
    cart[/cart — CRUD lines/]
    admin[/admin — products CRUD, health/]
  end

  Client((Client)) --> v1
```

---

## 4. Module dependencies (who calls whom)

```mermaid
flowchart LR
  subgraph routers
    A[auth]
    P[products]
    C[cart]
    AD[admin]
  end

  subgraph application
    AS[auth_service]
    PS[product_service]
    CS[cart_service]
  end

  A --> AS
  P --> PS
  C --> CS
  AD --> PS

  C --> ADU[deps: CurrentUser]
  AD --> ADU
  AD --> ADM[deps: AdminUser]
  A --> ADU

  CS --> DR[ecommerce_rules]
  PS --> DR
```

---

## 5. Data model (tables)

```mermaid
erDiagram
  users ||--o{ cart_items : has
  products ||--o{ cart_items : referenced_by
  users ||--o{ orders : places
  orders ||--o{ order_items : contains
  products ||--o{ order_items : snapshot
  orders ||--o| payments : has

  users {
    int id PK
    string email
    string hashed_password
    bool is_active
  }

  products {
    int id PK
    string name
    text description
    decimal price
    int stock_quantity
    bool is_active
  }

  cart_items {
    int id PK
    int user_id FK
    int product_id FK
    int quantity
  }

  orders {
    int id PK
    int user_id FK
    string status
  }

  order_items {
    int id PK
    int order_id FK
    int product_id FK
  }

  payments {
    int id PK
    int order_id FK
  }
```

Field names are illustrative; see `src/infrastructure/db/models/` for exact columns.

---

## 6. Repository layout (folders)

```text
src/
  api/                    # FastAPI entry, routers, schemas, HTTP deps
    main.py
    dependencies.py       # DbSession, SettingsDep
    v1/
      router.py
      routers/            # auth, products, cart, admin
      deps/               # CurrentUser, AdminUser
      schemas/
  application/            # Use cases (services)
    auth_service.py
    product_service.py
    cart_service.py
  domain/                 # Pure rules (no FastAPI / SQLAlchemy)
    ecommerce_rules.py
  infrastructure/         # DB, settings, JWT, passwords
    config/
    db/
    security/
```

---

## 7. External systems (local dev)

```mermaid
flowchart LR
  subgraph host [Your machine]
    API[FastAPI app]
  end

  PG[(PostgreSQL)]
  API --> PG
```

Future chapters (Stripe, etc.) add another box **Stripe** with webhooks back to the API.
