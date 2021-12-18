import React, { useRef, useState } from "react";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";

import { SessionsList } from "./SessionsList";
import { Observation } from "./Observation";

export const Main = () => {
  const [session, setSession] = useState<any>(null);

  if (session === null) {
    return <SessionsList onSessionChosen={setSession} />;
  }
  return (
    <Box
      sx={{
        width: "100%",
        height: "100vh",
      }}
    >
      <h3 className="panel-title">
        Livecoding playground &nbsp;
        <Button
          variant="outlined"
          color="error"
          onClick={() => setSession(null)}
        >
          Leave
        </Button>
      </h3>
      <Observation session={session} />
    </Box>
  );
};
