import React from "react";

interface MP3PlayerProps {
  src: string;
}
export const MP3Player = ({ src }: MP3PlayerProps) => {
  return <audio autoPlay src={src}></audio>;
};
