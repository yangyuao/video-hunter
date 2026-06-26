declare module "cytoscape-fcose" {
  // fcose ships no bundled types; it registers itself via cytoscape.use().
  const ext: cytoscape.Ext;
  export default ext;
}
