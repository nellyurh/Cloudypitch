import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { SportPage } from "./pages/SportPage";
import { MatchDetail } from "./pages/MatchDetail";
import { LeaguePage } from "./pages/LeaguePage";
import { WorldCupHub } from "./pages/WorldCupHub";
import { PredictionsHub } from "./pages/Predictions";
import { FantasyHub } from "./pages/Fantasy";
import { LegendCards } from "./pages/LegendCards";
import { PrizePoolsList, PrizePoolDetail } from "./pages/PrizePool";
import { Profile } from "./pages/Profile";
import { Leaderboards } from "./pages/Leaderboards";
import { SearchPage } from "./pages/Search";
import { SignIn } from "./pages/SignIn";
import { SignUp } from "./pages/SignUp";
import { AdminPanel } from "./pages/Admin";

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard sport="football" />} />
              <Route path="/sport/:sport" element={<SportPage />} />
              <Route path="/match/:id" element={<MatchDetail />} />
              <Route path="/league/:id" element={<LeaguePage />} />
              <Route path="/worldcup" element={<WorldCupHub />} />
              <Route path="/predictions" element={<PredictionsHub />} />
              <Route path="/fantasy" element={<FantasyHub />} />
              <Route path="/cards" element={<LegendCards />} />
              <Route path="/prize-pools" element={<PrizePoolsList />} />
              <Route path="/prize-pool/:id" element={<PrizePoolDetail />} />
              <Route path="/leaderboards" element={<Leaderboards />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/signin" element={<SignIn />} />
              <Route path="/signup" element={<SignUp />} />
              <Route path="/admin" element={<AdminPanel />} />
            </Routes>
          </Layout>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
