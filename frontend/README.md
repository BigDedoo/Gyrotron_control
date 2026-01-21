# Gyrotron Control System - Frontend

A modern, reactive Single Page Application (SPA) for monitoring and controlling high-power gyrotron devices. Built with **Vue 3** and **TypeScript**, designed for performance and reliability.

## 🚀 Technology Stack

-   **Framework**: [Vue.js 3](https://vuejs.org/) (Composition API)
-   **Build Tool**: [Vite](https://vitejs.dev/)
-   **State Management**: [Pinia](https://pinia.vuejs.org/)
-   **Language**: TypeScript
-   **Styling**: [Tailwind CSS](https://tailwindcss.com/)
-   **UI Primitives**: [Radix Vue](https://www.radix-vue.com/)
-   **Charting**: [Apache ECharts](https://echarts.apache.org/) (via `vue-echarts`)
-   **Icons**: `lucide-vue-next`

## 🛠️ Setup & Installation

### Prerequisites
-   Node.js 18.x or higher
-   Backend server running on `http://localhost:8000` (for API proxies)

### Installation

```bash
cd frontend
npm install
```

### Development Server

Start the development server with HMR (Hot Module Replacement):

```bash
npm run dev
```

The application will be available at `http://localhost:5173`.

### Production Build

Build the application for production:

```bash
npm run build
```

Previews the production build locally:

```bash
npm run preview
```

## 📂 Project Structure

```text
src/
├── components/         # Shared UI components
│   ├── ui/             # Radix + Tailwind primitive components (Button, Card, etc.)
│   └── ...             # Feature-specific components (GaugeCard, QuickStatus)
├── composables/        # Reusable state logic (useTelemetry)
├── stores/             # Global Pinia stores
│   ├── auth.ts         # User authentication & roles
│   └── startup.ts      # Startup wizard state persistence
├── views/              # Main page views (Dashboard, Power, Safety, etc.)
├── App.vue             # Root component & Layout
└── main.ts             # Application entry point (Pinia & Vue initialization)
```

## ✨ Key Features

-   **Real-time Telemetry**: Polling architecture (1Hz) to visualize Ion Pump/Heater voltage and current.
-   **LDAP Authentication**: Secure login against corporate Active Directory.
-   **Startup Sequencer**: Guided 7-step wizard for safe system power-up.
-   **State Persistence**: Tab switching does not lose wizard progress (handled by Pinia).
-   **Safety Monitoring**: Instant visual feedback for interlock faults.
