import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { SportPage } from "./pages/SportPage";
import { MatchDetail } from "./pages/MatchDetail";
import TeamView from "./pages/TeamView";
import { LeaguePage } from "./pages/LeaguePage";
import { WorldCupHub } from "./pages/WorldCupHub";
import { PredictionsHub } from "./pages/Predictions";
import { FantasyHub } from "./pages/Fantasy";
import BuildTeam from "./pages/BuildTeam";
import MyTeams from "./pages/MyTeams";
import GameEntries from "./pages/GameEntries";
import { LegendCards } from "./pages/LegendCards";
import { PrizePoolsList, PrizePoolDetail } from "./pages/PrizePool";
import { Profile } from "./pages/Profile";
import { Leaderboards } from "./pages/Leaderboards";
import { SearchPage } from "./pages/Search";
import { SignIn } from "./pages/SignIn";
import { SignUp } from "./pages/SignUp";
import { AdminPanel } from "./pages/Admin";
import { WalletPage } from "./pages/Wallet";
import { PaymentCallback } from "./pages/PaymentCallback";
import { PremiumPage } from "./pages/Premium";
import { ReferralsPage } from "./pages/Referrals";
import { ForgotPassword, ResetPassword, VerifyEmail } from "./pages/AuthPages";
import { InterstitialAd } from "./components/InterstitialAd";
import { AdHeadInjector } from "./components/AdHeadInjector";
import { registerAdServiceWorker } from "./lib/registerAdSw";

if (typeof window !== "undefined") {
  registerAdServiceWorker();
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AdHeadInjector/>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard sport="football" />} />
              <Route path="/sport/:sport" element={<SportPage />} />
              <Route path="/match/:id" element={<MatchDetail />} />
              <Route path="/team/:teamId" element={<TeamView />} />
              <Route path="/league/:id" element={<LeaguePage />} />
              <Route path="/worldcup" element={<WorldCupHub />} />
              <Route path="/predictions" element={<PredictionsHub />} />
              <Route path="/fantasy" element={<FantasyHub />} />
              <Route path="/fantasy/hub" element={<FantasyHub />} />
              <Route path="/build-team" element={<BuildTeam />} />
              <Route path="/my-teams" element={<MyTeams />} />
              <Route path="/wc/games/:gameId/entries" element={<GameEntries />} />
              <Route path="/cards" element={<LegendCards />} />
              <Route path="/prize-pools" element={<PrizePoolsList />} />
              <Route path="/prize-pool/:id" element={<PrizePoolDetail />} />
              <Route path="/leaderboards" element={<Leaderboards />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/signin" element={<SignIn />} />
              <Route path="/signup" element={<SignUp />} />
              <Route path="/admin" element={<AdminPanel />} />
              <Route path="/wallet" element={<WalletPage />} />
              <Route path="/premium" element={<PremiumPage />} />
              <Route path="/referrals" element={<ReferralsPage />} />
              <Route path="/payment/callback" element={<PaymentCallback />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/wc/games" element={<Navigate to="/fantasy" replace />} />
            </Routes>
            <InterstitialAd />
          </Layout>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
