import React, { useRef } from "react";
import Box from "@mui/material/Box";

interface SSHFrameProps {
  src: string;
}
export const SSHFrame = ({ src }: SSHFrameProps) => {
  const frame = useRef<HTMLIFrameElement>(null);
  return (
    <Box width="100%" height="100%">
      <iframe
        src={src}
        className="ssh-frame"
        ref={frame}
        width="100%"
        height="100%"
      />
    </Box>
  );
};
