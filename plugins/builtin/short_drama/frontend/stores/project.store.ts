import { reactive } from "vue";

export type ProjectRecord = { id:string; name:string; category:string; language:string };

export function createProjectStore(initialProjects:readonly ProjectRecord[], initialProjectId:string) {
  const state = reactive({
    projects:[...initialProjects] as ProjectRecord[],
    currentProjectId:initialProjects.some(item => item.id === initialProjectId) ? initialProjectId : initialProjects[0]?.id || "",
  });

  function replace(projects:readonly ProjectRecord[], currentProjectId = state.currentProjectId) {
    state.projects = [...projects];
    state.currentProjectId = projects.some(item => item.id === currentProjectId) ? currentProjectId : projects[0]?.id || "";
    return true;
  }

  function select(id:string) {
    if (!state.projects.some(item => item.id === id)) return false;
    state.currentProjectId = id;
    return true;
  }

  function add(project:ProjectRecord) {
    if (state.projects.some(item => item.id === project.id)) return false;
    state.projects.push({ ...project });
    state.currentProjectId = project.id;
    return true;
  }

  function remove(id:string) {
    if (state.projects.length <= 1 || !state.projects.some(item => item.id === id)) return false;
    state.projects = state.projects.filter(item => item.id !== id);
    if (state.currentProjectId === id) state.currentProjectId = state.projects[0].id;
    return true;
  }

  function current() {
    return state.projects.find(item => item.id === state.currentProjectId) || state.projects[0] || null;
  }

  function snapshot() {
    return { projects:state.projects.map(item => ({ ...item })), currentProjectId:state.currentProjectId };
  }

  return { state, replace, select, add, remove, current, snapshot };
}

export type ProjectStore = ReturnType<typeof createProjectStore>;
