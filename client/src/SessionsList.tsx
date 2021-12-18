import React, { useRef, useState, useEffect } from "react";
import Alert from "@mui/material/Alert";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Typography from "@mui/material/Typography";
import Divider from "@mui/material/Divider";
import AddIcon from "@mui/icons-material/Add";

const WS_HOST = `${window.location.hostname}:3001`;

interface Session {
  id: string;
  state: string;
}

interface SessionsListProps {
  onSessionChosen: (session: Session | { id: "new" }) => void;
}

export const SessionsList = ({ onSessionChosen }: SessionsListProps) => {
  const [ws, setWs] = useState<WebSocket | null>(null);

  const [allSessions, setSessions] = useState<Session[]>([]);
  const sessions = allSessions.filter((s) => s.state !== "stopping");

  const onMessage = (message: { command: string; session: Session }) => {
    console.log(message);
    console.log(sessions);

    if (message.command === "session_add") {
      setSessions((sessions) => [
        ...sessions,
        {
          id: message.session.id,
          state: message.session.state,
          timeout: null,
        },
      ]);
    } else if (message.command === "session_remove") {
      setSessions((sessions) =>
        sessions.filter((session) => session.id !== message.session.id)
      );
    } else if (message.command === "session_state") {
      setSessions((sessions) =>
        sessions.map((session) =>
          session.id !== message.session.id ? session : message.session
        )
      );
    }
  };

  useEffect(() => {
    const ws = new WebSocket(`ws://${WS_HOST}/watch_list`);
    // Connection opened
    ws.addEventListener("open", function (event: any) {
      console.log("opened");
    });

    // Listen for messages
    ws.addEventListener("message", function (event: any) {
      var json = JSON.parse(event.data);
      onMessage(json);
    });
    setWs(ws);
    return () => {
      ws.close();
      setWs(null);
    };
  }, []);

  return (
    <div className="panel panel-default">
      <div className="panel-heading">
        <h3 className="panel-title">Pick your playground</h3>
      </div>
      {sessions.length === 0 ? (
        <Alert severity="warning">
          You're the first one here. Start a new playground with a button below.
        </Alert>
      ) : (
        <Typography>
          There {sessions.length > 1 ? "are" : "is"} currently {sessions.length}{" "}
          active playground
          {sessions.length > 1 ? "s" : ""}. Pick one to join or create a new
          one.
        </Typography>
      )}
      <List>
        {sessions.map((session: Session) => (
          <ListItem key={session.id}>
            <ListItemButton
              onClick={
                session.state === "idle" || session.state === "running"
                  ? (e) => onSessionChosen(session)
                  : () => {}
              }
              href="#"
            >
              <ListItemText
                primary={`Playground: ${session.id} [${session.state}]`}
              ></ListItemText>
            </ListItemButton>
          </ListItem>
        ))}
        <Divider />
        <ListItem disablePadding>
          <ListItemButton onClick={(e) => onSessionChosen({ id: "new" })}>
            <ListItemIcon>
              <AddIcon />
            </ListItemIcon>
            <ListItemText>Start a new playground</ListItemText>
          </ListItemButton>
        </ListItem>
      </List>
    </div>
  );
};
