import React from "react";
import { useParams } from "react-router-dom";
import { Dashboard } from "./Dashboard";

export const SportPage = () => {
  const { sport } = useParams();
  return <Dashboard sport={sport} />;
};

export default SportPage;
