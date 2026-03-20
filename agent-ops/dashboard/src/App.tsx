import { DashboardLayout } from "./components/DashboardLayout";
import { ErrorBoundary } from "./components/ErrorBoundary";

export default function App() {
  return (
    <ErrorBoundary>
      <DashboardLayout />
    </ErrorBoundary>
  );
}
