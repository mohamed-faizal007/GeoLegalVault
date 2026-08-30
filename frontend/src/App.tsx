import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { PERMISSIONS } from "./lib/permissions";
import AdminPanel from "./pages/AdminPanel";
import AmendmentRequest from "./pages/AmendmentRequest";
import AuditLogs from "./pages/AuditLogs";
import BlockchainVerification from "./pages/BlockchainVerification";
import Dashboard from "./pages/Dashboard";
import DocumentDetails from "./pages/DocumentDetails";
import DocumentRepository from "./pages/DocumentRepository";
import Forbidden from "./pages/Forbidden";
import GeofenceStatus from "./pages/GeofenceStatus";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Settings from "./pages/Settings";
import Upload from "./pages/Upload";
import Verification from "./pages/Verification";
import VersionHistory from "./pages/VersionHistory";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/documents" element={<DocumentRepository />} />
        <Route
          path="/documents/upload"
          element={
            <ProtectedRoute permission={PERMISSIONS.DOCUMENT_UPLOAD}>
              <Upload />
            </ProtectedRoute>
          }
        />
        <Route path="/documents/:id" element={<DocumentDetails />} />
        <Route path="/documents/:id/versions" element={<VersionHistory />} />
        <Route
          path="/documents/:id/amend"
          element={
            <ProtectedRoute permission={PERMISSIONS.DOCUMENT_AMEND}>
              <AmendmentRequest />
            </ProtectedRoute>
          }
        />
        <Route
          path="/verify/:versionId"
          element={
            <ProtectedRoute permission={PERMISSIONS.VERIFY_PERFORM}>
              <Verification />
            </ProtectedRoute>
          }
        />
        <Route path="/versions/:versionId/blockchain" element={<BlockchainVerification />} />
        <Route path="/geofence-status" element={<GeofenceStatus />} />
        <Route
          path="/audit"
          element={
            <ProtectedRoute permission={PERMISSIONS.AUDIT_VIEW}>
              <AuditLogs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute permission={PERMISSIONS.USERS_MANAGE}>
              <AdminPanel />
            </ProtectedRoute>
          }
        />
        <Route path="/settings" element={<Settings />} />
        <Route path="/forbidden" element={<Forbidden />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
