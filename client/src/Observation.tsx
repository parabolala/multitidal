import React, { useState, useEffect } from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";

import { MP3Player } from "./MP3Player";
import { SSHFrame } from "./SSHFrame";

const WS_HOST = `${window.location.hostname}:3001`;

interface ObservationProps {
  session: {
    id: string;
  };
}

export const Observation = ({ session }: ObservationProps) => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [sshUrl, setSshUrl] = useState<string>("");
  const [mp3Url, setMp3Url] = useState<string>("");

  const onMessage = (data: {
    status: string;
    ssh: { url: string };
    mp3: { url: string };
  }) => {
    console.log("Got message");
    console.log(data);
    if (data.status === "connected") {
      setSshUrl(data.ssh.url);
      setMp3Url(data.mp3.url);
    }
  };

  useEffect(() => {
    const ws = new WebSocket("ws://" + WS_HOST + "/observe/" + session.id);

    ws.addEventListener("open", function (event: any) {
      console.log("opened");
    });

    // Listen for messages
    var that = this;
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

  if (sshUrl === "") {
    return (
      <div className="progress">
        <div
          className="progress-bar progress-bar-success progress-bar-striped active"
          role="progressbar"
          aria-valuenow={100}
          aria-valuemin={0}
          aria-valuemax={100}
          style={{ width: "100%" }}
        >
          Loading...
        </div>
      </div>
    );
  }
  return (
    <Box sx={{ width: "100%", height: "100%" }}>
      <MP3Player src={mp3Url} />
      <SSHFrame src={sshUrl} />
    </Box>
  );
};
